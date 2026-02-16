#!/usr/bin/env python3
"""
Agent 1: Content Generator
Fetches recent tenders from public schema, imports them into socode.tender_sources,
generates Twitter and LinkedIn content via TenderSummarizer, and inserts drafts into socode.social_posts.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.summarizer import TenderSummarizer
from utils.tendly_scraper import scrape_tender, extract_procurement_id

load_dotenv()


def get_db_engine():
    """Get database engine connection."""
    db_url = os.getenv("EE_DB_URL")
    if not db_url:
        raise RuntimeError("EE_DB_URL not found in environment variables")
    return create_engine(db_url)


def fetch_new_tenders(engine, days: int, limit: int, verbose: bool = False):
    """Fetch recent tenders not yet imported into socode.tender_sources."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    query = text("""
        SELECT
            t.procurement_id,
            t.procurement_reference_nr,
            t.procurement_name,
            t.contracting_authority_name,
            t.short_description,
            t.main_cpv_name,
            t.main_cpv_id,
            t.proc_process_submit_date,
            t.created_at,
            d.estimated_cost,
            d.document_url
        FROM public.estonian_tenders t
        LEFT JOIN public.estonian_tender_details d
            ON t.procurement_id = d.procurement_id
        WHERE t.created_at >= :cutoff
          AND t.procurement_id NOT IN (
              SELECT procurement_id FROM socode.tender_sources
          )
        ORDER BY t.created_at DESC
        LIMIT :limit
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"cutoff": cutoff, "limit": limit})
        rows = result.mappings().all()

    if verbose:
        print(f"  Fetched {len(rows)} new tenders from DB (last {days} days)")

    return rows


def import_tender_source(conn, row):
    """Insert a tender into socode.tender_sources."""
    budget = None
    if row.get("estimated_cost"):
        budget = f"EUR {row['estimated_cost']:,.0f}"

    deadline = row.get("proc_process_submit_date")

    cpv_codes = []
    if row.get("main_cpv_id"):
        cpv_codes.append(str(row["main_cpv_id"]))

    doc_url = row.get("document_url") or f"https://www.tendly.eu/tenders/{row.get('procurement_reference_nr', '')}"

    conn.execute(text("""
        INSERT INTO socode.tender_sources
            (procurement_id, procurement_reference_nr, title, organization,
             budget, deadline, category, description, cpv_codes,
             document_url, estimated_cost, source_created_at)
        VALUES
            (:pid, :ref_nr, :title, :org,
             :budget, :deadline, :category, :description, :cpv_codes,
             :doc_url, :est_cost, :src_created)
        ON CONFLICT (procurement_id) DO NOTHING
    """), {
        "pid": row["procurement_id"],
        "ref_nr": row.get("procurement_reference_nr", ""),
        "title": row.get("procurement_name", ""),
        "org": row.get("contracting_authority_name"),
        "budget": budget,
        "deadline": deadline,
        "category": row.get("main_cpv_name"),
        "description": row.get("short_description"),
        "cpv_codes": cpv_codes,
        "doc_url": doc_url,
        "est_cost": row.get("estimated_cost"),
        "src_created": row.get("created_at"),
    })


def build_tender_dict(row) -> dict:
    """Build the tender dict format expected by TenderSummarizer."""
    budget = None
    if row.get("estimated_cost"):
        budget = f"EUR {row['estimated_cost']:,.0f}"

    deadline = None
    if row.get("proc_process_submit_date"):
        dl = row["proc_process_submit_date"]
        deadline = dl.strftime("%Y-%m-%d") if hasattr(dl, "strftime") else str(dl)

    return {
        "title": row.get("procurement_name", ""),
        "organization": row.get("contracting_authority_name", ""),
        "budget": budget,
        "deadline": deadline,
        "category": row.get("main_cpv_name", ""),
        "description": row.get("short_description", ""),
    }


def insert_social_post(conn, procurement_id, content, hashtags, doc_url, platform="twitter"):
    """Insert a draft social post into socode.social_posts."""
    conn.execute(text("""
        INSERT INTO socode.social_posts
            (procurement_id, platform, content, hashtags, document_url, status)
        VALUES
            (:pid, :platform, :content, :hashtags, :doc_url, 'draft')
    """), {
        "pid": procurement_id,
        "platform": platform,
        "content": content,
        "hashtags": hashtags,
        "doc_url": doc_url,
    })


def process_url(url: str, engine, summarizer, dry_run: bool, verbose: bool):
    """Scrape a single tendly.eu URL and generate a social post for it."""
    if verbose:
        print(f"  Scraping URL: {url}")

    row = scrape_tender(url)
    pid = row["procurement_id"]
    title = row.get("procurement_name", "")

    if verbose:
        print(f"  Scraped tender: {title[:60]}...")

    with engine.connect() as conn:
        import_tender_source(conn, row)

        tender_dict = build_tender_dict(row)
        doc_url = url

        # Generate Twitter content
        if dry_run:
            tw_content = f"[DRY RUN] Would generate tweet for: {title[:80]}"
            hashtags = ["#PublicProcurement", "#Tenders", "#Tendly", "#Estonia"]
        else:
            tw_content = summarizer.summarize_for_twitter(tender_dict)
            hashtags = summarizer.create_hashtags(tender_dict)

        insert_social_post(conn, pid, tw_content, hashtags, doc_url, platform="twitter")

        if verbose:
            print(f"    Twitter ({len(tw_content)} chars): {tw_content[:100]}...")

        # Generate LinkedIn content
        if dry_run:
            li_content = f"[DRY RUN] Would generate LinkedIn post for: {title[:80]}"
        else:
            li_content = summarizer.summarize_for_linkedin(tender_dict)

        insert_social_post(conn, pid, li_content, hashtags, doc_url, platform="linkedin")

        if verbose:
            print(f"    LinkedIn ({len(li_content)} chars): {li_content[:100]}...")

        conn.commit()

    print(f"\nDone: 1 tender, 2 posts (Twitter + LinkedIn) generated from URL")


def main():
    parser = argparse.ArgumentParser(description="Generate social media content from recent tenders")
    parser.add_argument("--url", type=str, help="Scrape a single tendly.eu tender URL instead of querying the DB")
    parser.add_argument("--days", type=int, default=7, help="Lookback period in days (default: 7)")
    parser.add_argument("--limit", type=int, default=20, help="Max tenders to process (default: 20)")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, generate placeholder content")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    args = parser.parse_args()

    print("=== Content Generator ===")

    engine = get_db_engine()
    summarizer = None if args.dry_run else TenderSummarizer()

    # Single-URL mode: scrape and process one tender, then exit
    if args.url:
        print(f"Mode: single URL | Dry run: {args.dry_run}")
        process_url(args.url, engine, summarizer, args.dry_run, args.verbose)
        return

    print(f"Lookback: {args.days} days | Limit: {args.limit} | Dry run: {args.dry_run}")

    rows = fetch_new_tenders(engine, args.days, args.limit, args.verbose)

    generated = 0
    errors = 0

    with engine.connect() as conn:
        for row in rows:
            pid = row["procurement_id"]
            title = row.get("procurement_name", "")

            try:
                if args.verbose:
                    print(f"  Processing: {title[:60]}...")

                # Import tender source
                import_tender_source(conn, row)

                # Generate content
                tender_dict = build_tender_dict(row)
                doc_url = row.get("document_url") or f"https://www.tendly.eu/tenders/{row.get('procurement_reference_nr', '')}"

                if args.dry_run:
                    tw_content = f"[DRY RUN] Would generate tweet for: {title[:80]}"
                    li_content = f"[DRY RUN] Would generate LinkedIn post for: {title[:80]}"
                    hashtags = ["#PublicProcurement", "#Tenders", "#Tendly", "#Estonia"]
                else:
                    tw_content = summarizer.summarize_for_twitter(tender_dict)
                    li_content = summarizer.summarize_for_linkedin(tender_dict)
                    hashtags = summarizer.create_hashtags(tender_dict)

                # Insert draft posts for both platforms
                insert_social_post(conn, pid, tw_content, hashtags, doc_url, platform="twitter")
                insert_social_post(conn, pid, li_content, hashtags, doc_url, platform="linkedin")
                generated += 1

                if args.verbose:
                    print(f"    Twitter ({len(tw_content)} chars): {tw_content[:100]}...")
                    print(f"    LinkedIn ({len(li_content)} chars): {li_content[:100]}...")

            except Exception as e:
                errors += 1
                print(f"  ERROR processing tender {pid}: {e}")

        conn.commit()

    print(f"\nDone: {generated} generated, {errors} errors")


if __name__ == "__main__":
    main()
