"""Interactive TUI application for social media posting."""
import asyncio
import os
from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from dotenv import load_dotenv

from .components.command_processor import CommandProcessor, Command
from .components.social_handler import SocialMediaHandler


class SocialMediaTUI:
    """Interactive TUI for social media posting."""

    def __init__(self):
        self.cmd_processor = CommandProcessor()
        self.social_handler: Optional[SocialMediaHandler] = None
        self.console = Console()

        completions = [
            "channel:x", "channel:twitter", "channel:li", "channel:linkedin",
            "action:summarise", "action:summarize", "action:post", "action:preview",
            "url:", "content:",
            "help", "history", "clear", "exit", "quit",
        ]
        completer = WordCompleter(completions, ignore_case=True)

        kb = KeyBindings()

        @kb.add("c-l")
        def _clear(event):
            """Clear screen."""
            event.app.renderer.clear()

        self.session = PromptSession(
            history=InMemoryHistory(),
            completer=completer,
            key_bindings=kb,
            complete_while_typing=False,
        )

    def _init_handler(self) -> None:
        """Initialize the social media handler."""
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        try:
            self.social_handler = SocialMediaHandler()
            self.console.print("[green]Status:[/green] Ready - API keys configured")
        except ValueError as e:
            self.console.print(
                f"[red]Failed to initialize:[/red]\n{e}\n\n"
                "Please ensure .env file is configured with:\n"
                "- ARCADE_API_KEY\n"
                "- XAI_API_KEY\n"
                "- ARCADE_USER_EMAIL\n"
                "- ARCADE_USER_PASSWORD\n"
                "- ARCADE_USER_ID"
            )

    def _display_welcome(self) -> None:
        """Display welcome banner."""
        self.console.print(
            "\n[bold cyan]"
            "╔════════════════════════════════════════════════════════════╗\n"
            "║   Tendly Social Media Posting TUI                         ║\n"
            "╚════════════════════════════════════════════════════════════╝"
            "[/bold cyan]\n"
            "\n"
            "[yellow]Quick Start Examples:[/yellow]\n"
            "\n"
            "1. [cyan]Summarise and post to X:[/cyan]\n"
            "   channel:x action:summarise url:https://example.com/article\n"
            "\n"
            "2. [cyan]Post to LinkedIn:[/cyan]\n"
            "   channel:li action:post url:https://example.com content:\"Check this out!\"\n"
            "\n"
            "3. [cyan]Preview before posting:[/cyan]\n"
            "   channel:twitter action:preview url:https://example.com\n"
            "\n"
            "[yellow]Commands:[/yellow]\n"
            "  [cyan]help[/cyan]     - Show detailed help\n"
            "  [cyan]history[/cyan]  - Show command history\n"
            "  [cyan]clear[/cyan]    - Clear screen\n"
            "  [cyan]exit[/cyan]     - Exit application\n"
        )

    async def _handle_input(self, user_input: str) -> None:
        """Process a single line of user input."""
        text = user_input.strip()
        if not text:
            return

        lower = text.lower()

        if lower in ("help", "h", "?"):
            self.console.print(self.cmd_processor.get_help())
            return

        if lower in ("history", "hist"):
            history = self.cmd_processor.get_history()
            if history:
                self.console.print("[bold]Command History:[/bold]")
                for i, cmd in enumerate(history[-10:], 1):
                    self.console.print(f"  {i}. {cmd}")
            else:
                self.console.print("No command history yet.")
            return

        if lower in ("clear", "cls"):
            self.console.clear()
            return

        if lower in ("exit", "quit"):
            raise EOFError

        await self._execute_command(text)

    async def _execute_command(self, user_input: str) -> None:
        """Parse and execute a social media command."""
        try:
            self.console.print("[cyan]Status:[/cyan] Processing command...")

            cmd = self.cmd_processor.parse_command(user_input)

            if not cmd.is_valid:
                self.console.print(f"[red]Command Error:[/red] {cmd.error_message}")
                return

            self.console.print(
                f"[cyan]Parsed Command:[/cyan]\n"
                f"  Channel: {cmd.channel.value if cmd.channel else 'N/A'}\n"
                f"  Action: {cmd.action.value if cmd.action else 'N/A'}\n"
                f"  URL: {cmd.url or 'N/A'}\n"
                f"  Content: {cmd.content or 'N/A'}"
            )

            if not self.social_handler:
                self.console.print("[red]Error:[/red] Social media handler not initialized.")
                return

            self.console.print("[cyan]Status:[/cyan] Executing...")
            result = await self.social_handler.execute_command(cmd)

            if result.success:
                self.console.print(f"[green]Success![/green]")
                self.console.print(f"[cyan]Channel:[/cyan] {result.channel.upper()}")
                self.console.print(f"[cyan]Content:[/cyan]\n{result.content}")
                if result.post_url:
                    self.console.print(f"[cyan]Post URL:[/cyan] {result.post_url}")
            else:
                self.console.print(f"[red]Failed:[/red]\n[red]Error:[/red] {result.error}")

        except Exception as e:
            self.console.print(f"[red]Execution error: {e}[/red]")

    async def run(self) -> None:
        """Main REPL loop."""
        self._display_welcome()
        self._init_handler()

        with patch_stdout():
            while True:
                try:
                    user_input = await self.session.prompt_async("soco> ")
                    await self._handle_input(user_input)
                except (EOFError, KeyboardInterrupt):
                    self.console.print("\nGoodbye!")
                    break


async def run_tui():
    """Run the TUI application."""
    app = SocialMediaTUI()
    await app.run()


if __name__ == "__main__":
    asyncio.run(run_tui())
