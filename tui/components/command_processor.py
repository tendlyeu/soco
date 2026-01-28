"""Command processor for social media posting TUI."""
import re
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum


class Channel(Enum):
    """Supported social media channels."""
    X = "x"
    TWITTER = "twitter"
    LINKEDIN = "li"
    LINKEDIN_FULL = "linkedin"


class Action(Enum):
    """Supported actions."""
    SUMMARISE = "summarise"
    SUMMARIZE = "summarize"
    POST = "post"
    PREVIEW = "preview"


@dataclass
class Command:
    """Parsed command structure."""
    channel: Optional[Channel] = None
    action: Optional[Action] = None
    url: Optional[str] = None
    content: Optional[str] = None
    raw_input: str = ""
    is_valid: bool = False
    error_message: str = ""


class CommandProcessor:
    """Processes social media posting commands."""

    def __init__(self):
        self.history: List[str] = []
        self.channel_map = {
            "x": Channel.X,
            "twitter": Channel.TWITTER,
            "li": Channel.LINKEDIN,
            "linkedin": Channel.LINKEDIN_FULL,
        }
        self.action_map = {
            "summarise": Action.SUMMARISE,
            "summarize": Action.SUMMARIZE,
            "post": Action.POST,
            "preview": Action.PREVIEW,
        }

    def parse_command(self, user_input: str) -> Command:
        """
        Parse user input into a command structure.
        
        Supported formats:
        - channel:x action:summarise url:https://example.com
        - channel:li action:post url:https://example.com content:"My content"
        - channel:twitter action:preview url:https://example.com
        """
        cmd = Command(raw_input=user_input)
        
        if not user_input.strip():
            cmd.error_message = "Empty input"
            return cmd

        # Add to history
        self.history.append(user_input)

        # Parse key:value pairs
        try:
            parts = self._parse_key_value_pairs(user_input)
            
            # Extract channel
            if "channel" in parts:
                channel_str = parts["channel"].lower()
                if channel_str in self.channel_map:
                    cmd.channel = self.channel_map[channel_str]
                else:
                    cmd.error_message = f"Unknown channel: {channel_str}. Use: x, twitter, li, linkedin"
                    return cmd
            
            # Extract action
            if "action" in parts:
                action_str = parts["action"].lower()
                if action_str in self.action_map:
                    cmd.action = self.action_map[action_str]
                else:
                    cmd.error_message = f"Unknown action: {action_str}. Use: summarise, post, preview"
                    return cmd
            
            # Extract URL
            if "url" in parts:
                url = parts["url"].strip()
                if url.startswith("http://") or url.startswith("https://"):
                    cmd.url = url
                else:
                    cmd.error_message = "URL must start with http:// or https://"
                    return cmd
            
            # Extract content (optional)
            if "content" in parts:
                cmd.content = parts["content"].strip().strip('"\'')
            
            # Validate required fields
            if not cmd.channel:
                cmd.error_message = "Missing required field: channel"
                return cmd
            
            if not cmd.action:
                cmd.error_message = "Missing required field: action"
                return cmd
            
            if cmd.action in [Action.SUMMARISE, Action.SUMMARIZE, Action.PREVIEW]:
                if not cmd.url:
                    cmd.error_message = "URL required for summarise/preview actions"
                    return cmd
            
            if cmd.action == Action.POST:
                if not cmd.url and not cmd.content:
                    cmd.error_message = "Either URL or content required for post action"
                    return cmd
            
            cmd.is_valid = True
            return cmd
            
        except Exception as e:
            cmd.error_message = f"Parse error: {str(e)}"
            return cmd

    def _parse_key_value_pairs(self, user_input: str) -> Dict[str, str]:
        """
        Parse key:value pairs from input.
        Handles quoted values and URLs.
        """
        parts = {}
        
        # Pattern to match key:value pairs
        # Handles: key:value, key:"quoted value", key:https://url
        pattern = r'(\w+):(?:"([^"]*)"|\'([^\']*)\'|(\S+))'
        
        matches = re.finditer(pattern, user_input)
        for match in matches:
            key = match.group(1).lower()
            # Get the value from whichever group matched (quoted or unquoted)
            value = match.group(2) or match.group(3) or match.group(4)
            parts[key] = value
        
        return parts

    def normalize_channel(self, channel: Channel) -> str:
        """Normalize channel to standard name."""
        if channel in [Channel.X, Channel.TWITTER]:
            return "x"
        elif channel in [Channel.LINKEDIN, Channel.LINKEDIN_FULL]:
            return "linkedin"
        return channel.value

    def get_help(self) -> str:
        """Return help text for command syntax."""
        return """
╔════════════════════════════════════════════════════════════════╗
║           Social Media Posting TUI - Command Help             ║
╚════════════════════════════════════════════════════════════════╝

SYNTAX:
  channel:<channel> action:<action> url:<url> [content:"text"]

CHANNELS:
  • x, twitter        Post to X (Twitter)
  • li, linkedin      Post to LinkedIn

ACTIONS:
  • summarise         Generate AI summary from URL and post
  • post              Post content directly
  • preview           Preview content before posting

EXAMPLES:

1. Summarise and post to X:
   channel:x action:summarise url:https://example.com/article

2. Post to LinkedIn with custom content:
   channel:li action:post url:https://example.com content:"Check this out!"

3. Preview before posting to Twitter:
   channel:twitter action:preview url:https://example.com

COMMANDS:
  • help              Show this help message
  • history           Show command history
  • clear             Clear screen
  • exit, quit        Exit the application

NOTES:
  • URLs must start with http:// or https://
  • Use quotes for content with spaces: content:"My content here"
  • Channel aliases: x=twitter, li=linkedin
"""

    def get_history(self) -> List[str]:
        """Return command history."""
        return self.history.copy()
