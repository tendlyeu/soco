#!/usr/bin/env python3
"""
Pipeline Orchestrator
Runs all 3 agents (generate, review, post) as subprocesses.
Each agent runs in process isolation — if one fails, the pipeline reports and continues.
"""
import argparse
import subprocess
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).parent


def run_agent(name: str, cmd: list[str], skip: bool = False) -> bool:
    """Run a single agent as a subprocess. Returns True on success."""
    if skip:
        print(f"\n--- Skipping: {name} ---")
        return True

    print(f"\n{'=' * 50}")
    print(f"  Running: {name}")
    print(f"{'=' * 50}")

    try:
        result = subprocess.run(
            [sys.executable] + cmd,
            cwd=AGENTS_DIR.parent,  # Run from project root
        )
        if result.returncode != 0:
            print(f"\n[ERROR] {name} exited with code {result.returncode}")
            return False
        return True
    except Exception as e:
        print(f"\n[ERROR] {name} failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run the full tender-to-Twitter pipeline")
    parser.add_argument("--days", type=int, default=7, help="Lookback period for content generation (default: 7)")
    parser.add_argument("--limit", type=int, default=20, help="Max tenders to generate (default: 20)")
    parser.add_argument("--post-limit", type=int, default=5, help="Max tweets to post (default: 5)")
    parser.add_argument("--post-delay", type=int, default=10, help="Seconds between posts (default: 10)")
    parser.add_argument("--skip-generate", action="store_true", help="Skip content generation step")
    parser.add_argument("--skip-review", action="store_true", help="Skip interactive review step")
    parser.add_argument("--skip-post", action="store_true", help="Skip posting step")
    parser.add_argument("--url", type=str, help="Scrape a single tendly.eu tender URL instead of querying the DB")
    parser.add_argument("--dry-run", action="store_true", help="Pass --dry-run to generate and post agents")
    parser.add_argument("--verbose", action="store_true", help="Pass --verbose to all agents")
    args = parser.parse_args()

    print("=== Tendly Social Media Pipeline ===")

    results = {}

    # Agent 1: Generate content
    gen_cmd = [str(AGENTS_DIR / "generate_content.py")]
    if args.url:
        gen_cmd.extend(["--url", args.url])
    else:
        gen_cmd.extend(["--days", str(args.days), "--limit", str(args.limit)])
    if args.dry_run:
        gen_cmd.append("--dry-run")
    if args.verbose:
        gen_cmd.append("--verbose")
    results["generate"] = run_agent("Content Generator", gen_cmd, skip=args.skip_generate)

    # Agent 2: Review content (interactive — skip in dry-run)
    review_cmd = [str(AGENTS_DIR / "review_content.py")]
    if args.verbose:
        review_cmd.append("--verbose")
    skip_review = args.skip_review or args.dry_run
    results["review"] = run_agent("Content Reviewer", review_cmd, skip=skip_review)

    # Agent 3: Post to Twitter
    post_cmd = [
        str(AGENTS_DIR / "post_to_twitter.py"),
        "--limit", str(args.post_limit),
        "--delay", str(args.post_delay),
    ]
    if args.dry_run:
        post_cmd.append("--dry-run")
    if args.verbose:
        post_cmd.append("--verbose")
    results["post"] = run_agent("Twitter Poster", post_cmd, skip=args.skip_post)

    # Summary
    print(f"\n{'=' * 50}")
    print("  Pipeline Summary")
    print(f"{'=' * 50}")
    for name, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {name:.<20} {status}")

    all_ok = all(results.values())
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
