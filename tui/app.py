"""Main Textual TUI application for social media posting."""
import asyncio
import os
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult, on
from textual.containers import Vertical, Horizontal, Container
from textual.widgets import Header, Footer, Input, Static, Label, RichLog
from textual.binding import Binding
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown as RichMarkdown

from dotenv import load_dotenv

from .components.command_processor import CommandProcessor, Command
from .components.social_handler import SocialMediaHandler


class StatusPanel(Static):
    """Status panel showing current state."""
    
    def update_status(self, message: str, status_type: str = "info") -> None:
        """Update status with color coding."""
        color_map = {
            "info": "cyan",
            "success": "green",
            "error": "red",
            "warning": "yellow"
        }
        color = color_map.get(status_type, "cyan")
        self.update(f"[{color}]Status:[/{color}] {message}")


class OutputPanel(Static):
    """Output panel for displaying results."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.console = Console()
        self._content = ""
    
    def update(self, content: str = "") -> None:
        """Update content and store it for retrieval."""
        self._content = str(content)
        super().update(content)

    @property
    def renderable(self) -> str:
        """Return the current content."""
        return self._content
    
    def display_result(self, content: str, is_error: bool = False) -> None:
        """Display formatted result."""
        if is_error:
            self.update(f"[red]{content}[/red]")
        else:
            self.update(content)
    
    def display_help(self, help_text: str) -> None:
        """Display help text."""
        self.update(help_text)


class SocialMediaTUI(App):
    """Textual TUI for social media posting."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main_container {
        height: 1fr;
        padding: 1;
    }
    
    #output_view {
        height: 1fr;
        border: solid $accent;
        padding: 1;
        overflow-y: auto;
    }
    
    #status_bar {
        height: 3;
        padding: 1;
        background: $surface-lighten-1;
        color: $text;
        border-top: solid $primary;
    }
    
    #input_container {
        height: auto;
        dock: bottom;
        padding: 1;
    }
    
    Input {
        border: tall $primary;
    }
    
    Header {
        background: $primary;
        color: $text;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_output", "Clear", show=True),
        Binding("ctrl+h", "show_help", "Help", show=True),
    ]
    
    def __init__(self):
        super().__init__()
        self.cmd_processor = CommandProcessor()
        self.social_handler: Optional[SocialMediaHandler] = None
        self.console = Console()
    
    def compose(self) -> ComposeResult:
        """Compose the TUI layout."""
        yield Header(show_clock=True)
        
        with Vertical(id="main_container"):
            yield Label(
                "[bold cyan]📱 Tendly Social Media Posting TUI[/bold cyan] | "
                "[yellow]Channel:[/yellow] X, LinkedIn | "
                "[yellow]Actions:[/yellow] summarise, post, preview",
                id="intro"
            )
            yield OutputPanel(id="output_view")
        
        yield StatusPanel("Ready", id="status_bar")
        
        with Horizontal(id="input_container"):
            yield Input(
                placeholder="channel:x action:summarise url:https://... | Type 'help' for commands",
                id="query_input"
            )
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize when app starts."""
        # Load environment variables
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        
        # Initialize social media handler
        try:
            self.social_handler = SocialMediaHandler()
            self.query_one("#query_input", Input).focus()
            self._update_status("Ready - API keys configured", "success")
            self._display_welcome()
        except ValueError as e:
            self._update_status(f"Error: {str(e)}", "error")
            self._display_output(
                f"[red]Failed to initialize:[/red]\n{str(e)}\n\n"
                "Please ensure .env file is configured with:\n"
                "- ARCADE_API_KEY\n"
                "- XAI_API_KEY\n"
                "- ARCADE_USER_EMAIL\n"
                "- ARCADE_USER_PASSWORD\n"
                "- ARCADE_USER_ID"
            )
    
    @on(Input.Submitted)
    async def handle_input(self, event: Input.Submitted) -> None:
        """Handle user input."""
        user_input = event.value.strip()
        
        if not user_input:
            return
        
        # Clear input
        input_widget = self.query_one("#query_input", Input)
        input_widget.value = ""
        
        # Display user input
        self._display_output(f"[bold green]You:[/bold green] {user_input}\n")
        
        # Handle special commands
        if user_input.lower() in ["help", "h", "?"]:
            self._display_output(self.cmd_processor.get_help())
            return
        
        if user_input.lower() in ["history", "hist"]:
            history = self.cmd_processor.get_history()
            if history:
                hist_text = "Command History:\n" + "\n".join(f"{i+1}. {cmd}" for i, cmd in enumerate(history[-10:]))
                self._display_output(hist_text)
            else:
                self._display_output("No command history yet.")
            return
        
        if user_input.lower() in ["clear", "cls"]:
            self._clear_output()
            return
        
        if user_input.lower() in ["exit", "quit"]:
            self.exit()
            return
        
        # Parse and execute command
        await self._execute_command(user_input)
    
    async def _execute_command(self, user_input: str) -> None:
        """Parse and execute a social media command."""
        try:
            self._update_status("Processing command...", "info")
            
            # Parse command
            cmd = self.cmd_processor.parse_command(user_input)
            
            if not cmd.is_valid:
                self._display_output(f"[red]❌ Command Error:[/red] {cmd.error_message}")
                self._update_status(f"Error: {cmd.error_message}", "error")
                return
            
            # Display parsed command
            self._display_output(
                f"[cyan]Parsed Command:[/cyan]\n"
                f"  Channel: {cmd.channel.value if cmd.channel else 'N/A'}\n"
                f"  Action: {cmd.action.value if cmd.action else 'N/A'}\n"
                f"  URL: {cmd.url or 'N/A'}\n"
                f"  Content: {cmd.content or 'N/A'}\n"
            )
            
            # Execute command
            self._update_status("Executing...", "info")
            result = await self.social_handler.execute_command(cmd)
            
            # Display result
            if result.success:
                output = (
                    f"[green]✓ Success![/green]\n"
                    f"[cyan]Channel:[/cyan] {result.channel.upper()}\n"
                    f"[cyan]Content:[/cyan]\n{result.content}\n"
                )
                if result.post_url:
                    output += f"[cyan]Post URL:[/cyan] {result.post_url}\n"
                
                self._display_output(output)
                self._update_status(f"Posted to {result.channel.upper()}", "success")
            else:
                self._display_output(
                    f"[red]✗ Failed:[/red]\n"
                    f"[red]Error:[/red] {result.error}\n"
                )
                self._update_status(f"Error: {result.error}", "error")
        
        except Exception as e:
            error_msg = f"Execution error: {str(e)}"
            self._display_output(f"[red]❌ {error_msg}[/red]")
            self._update_status(error_msg, "error")
    
    def _display_output(self, content: str) -> None:
        """Display output in the output panel."""
        output_panel = self.query_one("#output_view", OutputPanel)
        current = output_panel.renderable
        
        # Append to existing content
        if current:
            output_panel.update(f"{current}\n{content}")
        else:
            output_panel.update(content)
        
        # Scroll to end
        output_panel.scroll_end(animate=False)
    
    def _display_welcome(self) -> None:
        """Display welcome message."""
        welcome = """
[bold cyan]╔════════════════════════════════════════════════════════════╗[/bold cyan]
[bold cyan]║   Tendly Social Media Posting TUI                         ║[/bold cyan]
[bold cyan]╚════════════════════════════════════════════════════════════╝[/bold cyan]

[yellow]Quick Start Examples:[/yellow]

1. [cyan]Summarise and post to X:[/cyan]
   channel:x action:summarise url:https://example.com/article

2. [cyan]Post to LinkedIn:[/cyan]
   channel:li action:post url:https://example.com content:"Check this out!"

3. [cyan]Preview before posting:[/cyan]
   channel:twitter action:preview url:https://example.com

[yellow]Commands:[/yellow]
  • [cyan]help[/cyan]     - Show detailed help
  • [cyan]history[/cyan]  - Show command history
  • [cyan]clear[/cyan]    - Clear screen
  • [cyan]exit[/cyan]     - Exit application

Type a command or press [bold]Ctrl+H[/bold] for help.
"""
        self._display_output(welcome)
    
    def _update_status(self, message: str, status_type: str = "info") -> None:
        """Update status bar."""
        status_panel = self.query_one("#status_bar", StatusPanel)
        status_panel.update_status(message, status_type)
    
    def _clear_output(self) -> None:
        """Clear the output panel."""
        output_panel = self.query_one("#output_view", OutputPanel)
        output_panel.update("")
    
    def action_clear_output(self) -> None:
        """Action to clear output."""
        self._clear_output()
    
    def action_show_help(self) -> None:
        """Action to show help."""
        self._display_output(self.cmd_processor.get_help())


async def run_tui():
    """Run the TUI application."""
    app = SocialMediaTUI()
    await app.run_async()


if __name__ == "__main__":
    asyncio.run(run_tui())
