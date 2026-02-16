#!/usr/bin/env python3
"""
Interactive Pipeline — step-by-step social media content creation.

Paste a tendly.eu URL, pick a platform, review/edit generated content,
and confirm posting — all within the terminal.
"""
import argparse
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.tendly_scraper import scrape_tender
from utils.summarizer import TenderSummarizer
from utils.social_poster import ArcadeSocialPoster
from agents.generate_content import (
    build_tender_dict,
    get_db_engine,
    import_tender_source,
    insert_social_post,
)

console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def select_option(title: str, options: list[tuple[str, str]], default: int = 0) -> str | None:
    """Arrow-key navigable inline menu.

    Args:
        title: Header printed above the menu (via Rich).
        options: List of (value, label) tuples.
        default: Index of the initially highlighted option.

    Returns:
        The *value* of the selected option, or None on cancel.
    """
    selected = [default]
    result: list[str | None] = [None]

    def get_text():
        lines = []
        for i, (_, label) in enumerate(options):
            marker = ">" if i == selected[0] else " "
            style = "bold reverse" if i == selected[0] else ""
            lines.append((style, f"  {marker} {i + 1}. {label}\n"))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    def _up(event):
        selected[0] = (selected[0] - 1) % len(options)

    @kb.add("down")
    def _down(event):
        selected[0] = (selected[0] + 1) % len(options)

    @kb.add("enter")
    def _enter(event):
        result[0] = options[selected[0]][0]
        event.app.exit()

    for idx in range(min(len(options), 9)):
        digit = str(idx + 1)

        @kb.add(digit)
        def _digit(event, i=idx):
            selected[0] = i
            result[0] = options[i][0]
            event.app.exit()

    @kb.add("c-c")
    def _cancel(event):
        event.app.exit()

    console.print(f"\n{title}")

    app: Application = Application(
        layout=Layout(HSplit([Window(FormattedTextControl(get_text), wrap_lines=True)])),
        key_bindings=kb,
        full_screen=False,
    )
    app.run()
    return result[0]


def edit_content(current: str, platform: str) -> str:
    """Open a multiline prompt pre-filled with *current* content."""
    console.print(
        f"\n[dim]Edit {platform} content below. Press [bold]Alt+Enter[/bold] when done.[/dim]"
    )
    session: PromptSession = PromptSession()
    edited = session.prompt("> ", default=current, multiline=True)
    return edited


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def interactive_pipeline(dry_run: bool = False, verbose: bool = False):
    # ── Welcome banner ──────────────────────────────────────────────
    console.print(
        Panel(
            "[bold]Tendly Social Pipeline[/bold]",
            style="cyan",
            expand=False,
        )
    )

    # ── URL input ───────────────────────────────────────────────────
    session: PromptSession = PromptSession()
    try:
        url = session.prompt(
            "\nPaste a tendly.eu URL:\n> ",
        ).strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled.[/dim]")
        return

    if not url:
        console.print("[red]No URL provided.[/red]")
        return

    # ── Scrape ──────────────────────────────────────────────────────
    console.print("\n[bold]Scraping tender...[/bold]")
    try:
        row = scrape_tender(url)
    except Exception as exc:
        console.print(f"[red]Scrape failed:[/red] {exc}")
        return

    tender_dict = build_tender_dict(row)

    # ── Display tender info ─────────────────────────────────────────
    tbl = Table(show_header=False, box=None, padding=(0, 2))
    tbl.add_column(style="bold")
    tbl.add_column()
    tbl.add_row("Title:", tender_dict.get("title") or "—")
    tbl.add_row("Organization:", tender_dict.get("organization") or "—")
    tbl.add_row("Budget:", tender_dict.get("budget") or "—")
    tbl.add_row("Deadline:", tender_dict.get("deadline") or "—")
    tbl.add_row("Category:", tender_dict.get("category") or "—")
    console.print()
    console.print(tbl)

    # ── DB: import tender source ────────────────────────────────────
    engine = None
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            import_tender_source(conn, row)
            conn.commit()
        if verbose:
            console.print("[dim]Tender saved to DB.[/dim]")
    except Exception as exc:
        if verbose:
            console.print(f"[dim]DB import skipped: {exc}[/dim]")

    # ── Platform selection ──────────────────────────────────────────
    platform_choice = select_option(
        "Select platform:",
        [("x", "X / Twitter"), ("linkedin", "LinkedIn"), ("both", "Both")],
    )
    if platform_choice is None:
        console.print("\n[dim]Cancelled.[/dim]")
        return

    platforms: list[str] = (
        ["x", "linkedin"] if platform_choice == "both" else [platform_choice]
    )

    # ── Generate content ────────────────────────────────────────────
    console.print("\n[bold]Generating content...[/bold]")

    summarizer = None
    if not dry_run:
        try:
            summarizer = TenderSummarizer()
        except Exception as exc:
            console.print(f"[red]Cannot init summarizer:[/red] {exc}")
            return

    generated: dict[str, str] = {}
    hashtags: list[str] = []

    for plat in platforms:
        if dry_run:
            if plat == "x":
                generated["x"] = f"[DRY RUN] Tweet for: {tender_dict['title'][:80]}"
            else:
                generated["linkedin"] = (
                    f"[DRY RUN] LinkedIn post for: {tender_dict['title'][:80]}"
                )
            hashtags = ["#PublicProcurement", "#Tenders", "#Tendly", "#Estonia"]
        else:
            if plat == "x":
                generated["x"] = summarizer.summarize_for_twitter(tender_dict)
            else:
                generated["linkedin"] = summarizer.summarize_for_linkedin(tender_dict)
            if not hashtags:
                hashtags = summarizer.create_hashtags(tender_dict)

    # ── Review loop (per platform) ──────────────────────────────────
    approved: dict[str, str] = {}

    for plat in platforms:
        content = generated[plat]
        label = "X / Twitter" if plat == "x" else "LinkedIn"
        char_limit = 280 if plat == "x" else 3000

        while True:
            # Show content panel
            console.print()
            console.print(
                Panel(
                    content,
                    title=f"{label} ({len(content)}/{char_limit} chars)",
                    border_style="green" if len(content) <= char_limit else "red",
                )
            )

            action = select_option(
                "Action:",
                [("approve", "Approve"), ("edit", "Edit"), ("reject", "Reject")],
            )

            if action == "approve":
                approved[plat] = content
                break
            elif action == "edit":
                content = edit_content(content, label)
                continue  # loop back to show updated content
            else:
                # reject or cancel
                console.print(f"[dim]{label} skipped.[/dim]")
                break

    if not approved:
        console.print("\n[dim]Nothing to post.[/dim]")
        return

    # ── DB: save drafts ─────────────────────────────────────────────
    if engine:
        try:
            with engine.connect() as conn:
                for plat, content in approved.items():
                    db_platform = "twitter" if plat == "x" else "linkedin"
                    insert_social_post(
                        conn,
                        row["procurement_id"],
                        content,
                        hashtags,
                        url,
                        platform=db_platform,
                    )
                conn.commit()
            if verbose:
                console.print("[dim]Drafts saved to DB.[/dim]")
        except Exception as exc:
            if verbose:
                console.print(f"[dim]DB draft save skipped: {exc}[/dim]")

    # ── Post confirmation & posting ─────────────────────────────────
    poster = None
    if not dry_run:
        try:
            poster = ArcadeSocialPoster()
        except Exception as exc:
            console.print(f"[red]Cannot init poster:[/red] {exc}")
            console.print("[dim]Content was approved but not posted.[/dim]")
            return

    results: list[dict] = []

    for plat, content in approved.items():
        label = "X / Twitter" if plat == "x" else "LinkedIn"
        confirm = select_option(
            f"Post to {label}?",
            [("yes", "Yes"), ("no", "No")],
        )
        if confirm != "yes":
            console.print(f"[dim]{label} posting skipped.[/dim]")
            continue

        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] would post to {label}.")
            results.append({"platform": plat, "success": True, "dry_run": True})
        else:
            console.print(f"Posting to {label}...", end=" ")
            if plat == "x":
                res = poster.post_to_twitter(content, url)
            else:
                res = poster.post_to_linkedin(content, url)
            if res.get("success"):
                console.print("[green]done![/green]")
            else:
                console.print(f"[red]failed:[/red] {res.get('error', 'unknown')}")
            results.append(res)

    # ── Summary ─────────────────────────────────────────────────────
    console.print()
    posted = sum(1 for r in results if r.get("success"))
    skipped = len(approved) - len(results)
    failed = len(results) - posted

    parts = []
    if posted:
        parts.append(f"[green]{posted} posted[/green]")
    if skipped:
        parts.append(f"[yellow]{skipped} skipped[/yellow]")
    if failed:
        parts.append(f"[red]{failed} failed[/red]")

    console.print(Panel(", ".join(parts) or "Nothing posted.", title="Summary", expand=False))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Interactive social media pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls for generation and posting")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    args = parser.parse_args()

    try:
        interactive_pipeline(dry_run=args.dry_run, verbose=args.verbose)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")


if __name__ == "__main__":
    main()
