#!/usr/bin/env python3
"""
Agent 2: Interactive Content Reviewer
Reads draft posts from socode.social_posts, displays tender info and generated
social media content, lets user approve, edit, skip, or reject each draft.
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import create_engine, text

load_dotenv()

console = Console()


def get_db_engine():
    db_url = os.getenv("EE_DB_URL")
    if not db_url:
        raise RuntimeError("EE_DB_URL not found in environment variables")
    return create_engine(db_url)


def fetch_drafts(engine):
    """Fetch all draft social posts joined with tender source info."""
    query = text("""
        SELECT
            sp.id AS post_id,
            sp.platform,
            sp.content,
            sp.hashtags,
            sp.document_url,
            sp.char_count,
            sp.generated_at,
            ts.procurement_id,
            ts.procurement_reference_nr,
            ts.title,
            ts.organization,
            ts.budget,
            ts.deadline,
            ts.category,
            ts.description
        FROM socode.social_posts sp
        JOIN socode.tender_sources ts ON sp.procurement_id = ts.procurement_id
        WHERE sp.status = 'draft'
        ORDER BY sp.generated_at
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        return result.mappings().all()


def display_draft(draft, index: int, total: int):
    """Display a single draft with rich formatting."""
    console.print()
    console.rule(f"[bold blue]Draft {index}/{total}[/bold blue]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan", width=14)
    table.add_column("Value")

    table.add_row("Title", draft.get("title") or "N/A")
    table.add_row("Organization", draft.get("organization") or "N/A")
    table.add_row("Budget", draft.get("budget") or "Not specified")
    deadline = draft.get("deadline")
    table.add_row("Deadline", str(deadline) if deadline else "Not specified")
    table.add_row("Category", draft.get("category") or "N/A")
    table.add_row("Ref Nr", draft.get("procurement_reference_nr") or "N/A")

    console.print(table)

    desc = draft.get("description") or ""
    if desc:
        console.print()
        console.print(Panel(desc[:500], title="Description", border_style="dim"))

    platform = draft.get("platform", "twitter")
    platform_label = "Twitter" if platform == "twitter" else "LinkedIn"
    max_chars = 280 if platform == "twitter" else 1000

    content = draft.get("content", "")
    char_count = draft.get("char_count") or len(content)
    color = "green" if char_count <= max_chars else "red"

    console.print()
    console.print(Panel(content, title=f"{platform_label} Content [{char_count}/{max_chars} chars]", border_style=color))

    hashtags = draft.get("hashtags") or []
    if hashtags:
        console.print(f"  Hashtags: {' '.join(hashtags)}")

    url = draft.get("document_url", "")
    if url:
        console.print(f"  URL: {url}")


def approve_post(conn, post_id):
    conn.execute(text("""
        UPDATE socode.social_posts
        SET status = 'approved', reviewed_at = NOW()
        WHERE id = :id
    """), {"id": post_id})
    conn.execute(text("""
        INSERT INTO socode.post_log (social_post_id, action, details)
        VALUES (:id, 'approved', '{"source": "review_content"}'::jsonb)
    """), {"id": post_id})


def reject_post(conn, post_id):
    conn.execute(text("""
        UPDATE socode.social_posts
        SET status = 'rejected', reviewed_at = NOW()
        WHERE id = :id
    """), {"id": post_id})
    conn.execute(text("""
        INSERT INTO socode.post_log (social_post_id, action, details)
        VALUES (:id, 'rejected', '{"source": "review_content"}'::jsonb)
    """), {"id": post_id})


def edit_post(conn, post_id, platform: str = "twitter") -> str | None:
    """Let user edit the post content. Returns new content or None."""
    platform_label = "Twitter" if platform == "twitter" else "LinkedIn"
    max_chars = 280 if platform == "twitter" else 1000
    console.print(f"\n[bold yellow]Enter new {platform_label} content (max {max_chars} chars):[/bold yellow]")
    console.print("[dim]Press Enter twice to finish:[/dim]")

    lines = []
    while True:
        line = input()
        if line == "" and lines:
            break
        lines.append(line)

    new_content = "\n".join(lines).strip()
    if not new_content:
        console.print("[dim]No changes made.[/dim]")
        return None

    conn.execute(text("""
        UPDATE socode.social_posts SET content = :content WHERE id = :id
    """), {"id": post_id, "content": new_content})

    char_count = len(new_content)
    color = "green" if char_count <= max_chars else "red"
    console.print(f"\n[{color}]Updated content ({char_count} chars):[/{color}]")
    console.print(Panel(new_content, border_style=color))
    return new_content


def main():
    parser = argparse.ArgumentParser(description="Review and approve generated social media content")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    args = parser.parse_args()

    console.print("[bold]=== Content Reviewer ===[/bold]")

    engine = get_db_engine()
    drafts = fetch_drafts(engine)

    if not drafts:
        console.print("[yellow]No drafts found in socode.social_posts[/yellow]")
        return

    console.print(f"Found [bold]{len(drafts)}[/bold] draft(s) to review.\n")

    approved = 0
    skipped = 0
    rejected = 0
    total = len(drafts)

    with engine.connect() as conn:
        for i, draft in enumerate(drafts, 1):
            post_id = draft["post_id"]
            display_draft(draft, i, total)

            while True:
                console.print()
                choice = console.input(
                    "[bold][A][/bold]pprove  [bold][E][/bold]dit  "
                    "[bold][S][/bold]kip  [bold][R][/bold]eject  [bold][Q][/bold]uit > "
                ).strip().lower()

                if choice in ("a", "approve"):
                    approve_post(conn, post_id)
                    conn.commit()
                    console.print(f"[green]Approved post #{post_id}[/green]")
                    approved += 1
                    break

                elif choice in ("e", "edit"):
                    edit_post(conn, post_id, draft.get("platform", "twitter"))
                    conn.commit()
                    continue

                elif choice in ("s", "skip"):
                    console.print("[dim]Skipped (stays as draft)[/dim]")
                    skipped += 1
                    break

                elif choice in ("r", "reject"):
                    reject_post(conn, post_id)
                    conn.commit()
                    console.print("[red]Rejected post #{post_id}[/red]")
                    rejected += 1
                    break

                elif choice in ("q", "quit"):
                    console.print("\n[bold]Quitting review.[/bold]")
                    remaining = total - i - approved - skipped - rejected + 1
                    console.print(
                        f"Session: {approved} approved, {skipped} skipped, "
                        f"{rejected} rejected, {remaining} remaining"
                    )
                    return

                else:
                    console.print("[dim]Invalid choice. Use A/E/S/R/Q.[/dim]")

    console.print()
    console.rule("[bold]Review Complete[/bold]")
    console.print(f"  Approved: {approved}")
    console.print(f"  Skipped:  {skipped}")
    console.print(f"  Rejected: {rejected}")


if __name__ == "__main__":
    main()
