#!/usr/bin/env python3
"""
soco - Tendly Social Code CLI

Central entry point for all soco commands. Run `python soco.py help` to see
available commands, or `python soco.py <command> --help` for command-specific options.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
AGENTS = ROOT / "agents"

COMMANDS = {
    "generate": {
        "script": AGENTS / "generate_content.py",
        "summary": "Generate social media content (Twitter + LinkedIn) from recent tenders",
        "usage": "python soco.py generate [--url URL] [--days N] [--limit N] [--dry-run] [--verbose]",
        "options": [
            ("--url URL", "Scrape a single tendly.eu tender URL instead of querying the DB"),
            ("--days N", "Lookback period in days (default: 7)"),
            ("--limit N", "Max tenders to process (default: 20)"),
            ("--dry-run", "Skip API calls, generate placeholder content"),
            ("--verbose", "Print detailed progress"),
        ],
    },
    "review": {
        "script": AGENTS / "review_content.py",
        "summary": "Interactively review, edit, approve, or reject draft posts",
        "usage": "python soco.py review [--verbose]",
        "options": [
            ("--verbose", "Print detailed progress"),
        ],
    },
    "post": {
        "script": AGENTS / "post_content.py",
        "summary": "Post approved content to Twitter and/or LinkedIn",
        "usage": "python soco.py post [--platform PLATFORM] [--limit N] [--delay N] [--dry-run] [--verbose]",
        "options": [
            ("--platform {twitter,linkedin,all}", "Platform to post to (default: all)"),
            ("--limit N", "Max posts per run (default: 5)"),
            ("--delay N", "Seconds between posts (default: 10)"),
            ("--dry-run", "Simulate posting without API calls"),
            ("--verbose", "Print detailed progress"),
        ],
    },
    "pipeline": {
        "script": AGENTS / "run_pipeline.py",
        "summary": "Run the full pipeline: generate -> review -> post",
        "usage": "python soco.py pipeline [--platform PLATFORM] [--days N] [--limit N] [--dry-run] [--verbose] [...]",
        "options": [
            ("--days N", "Lookback period for content generation (default: 7)"),
            ("--limit N", "Max tenders to generate (default: 20)"),
            ("--post-limit N", "Max posts per platform (default: 5)"),
            ("--post-delay N", "Seconds between posts (default: 10)"),
            ("--platform {twitter,linkedin,all}", "Platform to post to (default: all)"),
            ("--url URL", "Scrape a single tendly.eu tender URL"),
            ("--skip-generate", "Skip content generation step"),
            ("--skip-review", "Skip interactive review step"),
            ("--skip-post", "Skip posting step"),
            ("--dry-run", "Pass --dry-run to generate and post agents"),
            ("--verbose", "Pass --verbose to all agents"),
        ],
    },
    "run": {
        "script": AGENTS / "interactive_pipeline.py",
        "summary": "Interactive pipeline: scrape, generate, review, and post step by step",
        "usage": "python soco.py run [--dry-run] [--verbose]",
        "options": [
            ("--dry-run", "Skip API calls for generation and posting"),
            ("--verbose", "Print detailed progress"),
        ],
    },
    "tui": {
        "script": ROOT / "tui_main.py",
        "summary": "Launch the interactive TUI for social media posting",
        "usage": "python soco.py tui",
        "options": [],
    },
    "web": {
        "script": ROOT / "Home.py",
        "summary": "Launch the Streamlit web dashboard",
        "usage": "python soco.py web",
        "runner": "streamlit",
        "options": [],
    },
}


def print_help():
    print("soco - Tendly Social Code CLI\n")
    print("Usage: python soco.py <command> [options]\n")
    print("Commands:")
    max_name = max(len(name) for name in COMMANDS)
    for name, info in COMMANDS.items():
        print(f"  {name:<{max_name + 2}} {info['summary']}")
    print(f"\n  {'help':<{max_name + 2}} Show this help message")
    print(f"\nRun 'python soco.py <command> --help' for command-specific options.")


def print_command_help(name: str):
    info = COMMANDS[name]
    print(f"{name} - {info['summary']}\n")
    print(f"Usage: {info['usage']}\n")
    if info["options"]:
        print("Options:")
        max_opt = max(len(opt) for opt, _ in info["options"])
        for opt, desc in info["options"]:
            print(f"  {opt:<{max_opt + 2}} {desc}")
    print()


def main():
    if len(sys.argv) < 2:
        cmd = "run"
    elif sys.argv[1] in ("help", "--help", "-h"):
        print_help()
        return
    else:
        cmd = sys.argv[1]

    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Run 'python soco.py help' for available commands.")
        sys.exit(1)

    info = COMMANDS[cmd]
    extra_args = sys.argv[2:]

    if "--help" in extra_args or "-h" in extra_args:
        print_command_help(cmd)
        return

    runner = info.get("runner")
    if runner == "streamlit":
        run_cmd = [sys.executable, "-m", "streamlit", "run", str(info["script"])] + extra_args
    else:
        run_cmd = [sys.executable, str(info["script"])] + extra_args

    result = subprocess.run(run_cmd, cwd=ROOT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
