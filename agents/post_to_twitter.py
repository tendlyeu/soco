#!/usr/bin/env python3
"""
Agent 3: Twitter/X Poster
Reads approved posts from socode.social_posts, posts to Twitter/X via
ArcadeSocialPoster, updates status to 'posted', and logs results.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.social_poster import ArcadeSocialPoster

load_dotenv()


def get_db_engine():
    db_url = os.getenv("EE_DB_URL")
    if not db_url:
        raise RuntimeError("EE_DB_URL not found in environment variables")
    return create_engine(db_url)


def fetch_approved(engine, limit: int):
    """Fetch approved social posts ready to be posted."""
    query = text("""
        SELECT
            sp.id AS post_id,
            sp.procurement_id,
            sp.content,
            sp.hashtags,
            sp.document_url,
            sp.char_count,
            ts.title,
            ts.procurement_reference_nr
        FROM socode.social_posts sp
        JOIN socode.tender_sources ts ON sp.procurement_id = ts.procurement_id
        WHERE sp.status = 'approved'
        ORDER BY sp.reviewed_at
        LIMIT :limit
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"limit": limit})
        return result.mappings().all()


def mark_posted(conn, post_id, response: dict):
    """Mark a post as posted and log the result."""
    conn.execute(text("""
        UPDATE socode.social_posts
        SET status = 'posted', posted_at = NOW(), post_response = :response
        WHERE id = :id
    """), {"id": post_id, "response": json.dumps(response)})

    conn.execute(text("""
        INSERT INTO socode.post_log (social_post_id, action, details)
        VALUES (:id, 'posted', :details)
    """), {"id": post_id, "details": json.dumps({"response": response})})


def mark_failed(conn, post_id, error: str):
    """Mark a post as failed and log the error."""
    conn.execute(text("""
        UPDATE socode.social_posts
        SET status = 'failed', error_message = :error
        WHERE id = :id
    """), {"id": post_id, "error": error})

    conn.execute(text("""
        INSERT INTO socode.post_log (social_post_id, action, details)
        VALUES (:id, 'failed', :details)
    """), {"id": post_id, "details": json.dumps({"error": error})})


def main():
    parser = argparse.ArgumentParser(description="Post approved content to Twitter/X")
    parser.add_argument("--delay", type=int, default=10, help="Seconds between posts (default: 10)")
    parser.add_argument("--limit", type=int, default=5, help="Max posts per run (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate posting without API calls")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    args = parser.parse_args()

    print("=== Twitter Poster ===")
    print(f"Delay: {args.delay}s | Limit: {args.limit} | Dry run: {args.dry_run}")

    engine = get_db_engine()
    poster = None if args.dry_run else ArcadeSocialPoster()

    approved = fetch_approved(engine, args.limit)
    if not approved:
        print("No approved posts found in socode.social_posts")
        return

    print(f"Found {len(approved)} approved post(s)")

    posted = 0
    failed = 0

    with engine.connect() as conn:
        for i, post in enumerate(approved):
            post_id = post["post_id"]
            content = post["content"]
            url = post.get("document_url", "")
            title = post.get("title", "")

            if args.verbose:
                print(f"  Posting #{post_id}: {title[:60]}...")
                print(f"  Content ({post.get('char_count', len(content))} chars): {content[:100]}...")

            try:
                if args.dry_run:
                    print(f"  [DRY RUN] Would post tweet #{post_id}")
                    result = {"success": True, "dry_run": True}
                    mark_posted(conn, post_id, result)
                else:
                    result = poster.post_to_twitter(content, url)
                    if result.get("success"):
                        mark_posted(conn, post_id, result)
                        posted += 1
                        print(f"  Posted #{post_id}")
                    else:
                        error = result.get("error", "Unknown error")
                        mark_failed(conn, post_id, error)
                        failed += 1
                        print(f"  FAILED #{post_id}: {error}")

                conn.commit()

            except Exception as e:
                mark_failed(conn, post_id, str(e))
                conn.commit()
                failed += 1
                print(f"  ERROR #{post_id}: {e}")

            # Delay between posts
            if i < len(approved) - 1 and args.delay > 0 and not args.dry_run:
                print(f"  Waiting {args.delay}s...")
                time.sleep(args.delay)

    print(f"\nDone: {posted} posted, {failed} failed")


if __name__ == "__main__":
    main()
