#!/usr/bin/env python3
"""
Agent 3: Social Media Poster
Reads approved posts from socode.social_posts, posts to Twitter/X and LinkedIn
via ArcadeSocialPoster, updates status to 'posted', and logs results.
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


def fetch_approved(engine, limit: int, platform: str = "all"):
    """Fetch approved social posts ready to be posted, optionally filtered by platform."""
    if platform == "all":
        query = text("""
            SELECT
                sp.id AS post_id,
                sp.procurement_id,
                sp.platform,
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
        params = {"limit": limit}
    else:
        query = text("""
            SELECT
                sp.id AS post_id,
                sp.procurement_id,
                sp.platform,
                sp.content,
                sp.hashtags,
                sp.document_url,
                sp.char_count,
                ts.title,
                ts.procurement_reference_nr
            FROM socode.social_posts sp
            JOIN socode.tender_sources ts ON sp.procurement_id = ts.procurement_id
            WHERE sp.status = 'approved'
              AND sp.platform = :platform
            ORDER BY sp.reviewed_at
            LIMIT :limit
        """)
        params = {"limit": limit, "platform": platform}

    with engine.connect() as conn:
        result = conn.execute(query, params)
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


def post_item(poster, post, dry_run: bool, verbose: bool) -> dict:
    """Post a single item to the appropriate platform. Returns result dict."""
    platform = post.get("platform", "twitter")
    post_id = post["post_id"]
    content = post["content"]
    url = post.get("document_url", "")
    title = post.get("title", "")
    platform_label = "Twitter" if platform == "twitter" else "LinkedIn"

    if verbose:
        print(f"  [{platform_label}] Posting #{post_id}: {title[:60]}...")
        print(f"  Content ({post.get('char_count', len(content))} chars): {content[:100]}...")

    if dry_run:
        print(f"  [DRY RUN] Would post to {platform_label} #{post_id}")
        return {"success": True, "dry_run": True, "platform": platform}

    if platform == "linkedin":
        page_id = os.getenv("LINKEDIN_PAGE")
        return poster.post_to_linkedin(content, url, page_id=page_id)
    else:
        return poster.post_to_twitter(content, url)


def main():
    parser = argparse.ArgumentParser(description="Post approved content to social media")
    parser.add_argument("--platform", choices=["twitter", "linkedin", "all"], default="all",
                        help="Platform to post to (default: all)")
    parser.add_argument("--delay", type=int, default=10, help="Seconds between posts (default: 10)")
    parser.add_argument("--limit", type=int, default=5, help="Max posts per run (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate posting without API calls")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    args = parser.parse_args()

    platform_label = args.platform.capitalize() if args.platform != "all" else "All Platforms"
    print(f"=== Social Media Poster ({platform_label}) ===")
    print(f"Delay: {args.delay}s | Limit: {args.limit} | Dry run: {args.dry_run}")

    engine = get_db_engine()
    poster = None if args.dry_run else ArcadeSocialPoster()

    approved = fetch_approved(engine, args.limit, args.platform)
    if not approved:
        print("No approved posts found in socode.social_posts")
        return

    print(f"Found {len(approved)} approved post(s)")

    posted = 0
    failed = 0

    with engine.connect() as conn:
        for i, post in enumerate(approved):
            post_id = post["post_id"]

            try:
                result = post_item(poster, post, args.dry_run, args.verbose)

                if args.dry_run:
                    mark_posted(conn, post_id, result)
                elif result.get("success"):
                    mark_posted(conn, post_id, result)
                    posted += 1
                    platform = post.get("platform", "twitter")
                    print(f"  Posted #{post_id} to {platform}")
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
