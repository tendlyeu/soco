#!/usr/bin/env python3
"""Integration tests for social media handler."""
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from tui.components.command_processor import CommandProcessor, Channel, Action
from tui.components.social_handler import SocialMediaHandler


async def test_social_handler():
    """Test social media handler initialization and command execution."""
    
    # Load environment variables
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print("❌ .env file not found. Please create .env with required credentials.")
        return
    
    print("=" * 70)
    print("Testing Social Media Handler")
    print("=" * 70)
    
    # Test handler initialization
    print("\n1. Testing Handler Initialization...")
    try:
        handler = SocialMediaHandler()
        print("   ✓ Handler initialized successfully")
    except ValueError as e:
        print(f"   ❌ Failed to initialize handler: {e}")
        return
    
    # Test command parsing and validation
    print("\n2. Testing Command Parsing...")
    processor = CommandProcessor()
    
    test_commands = [
        "channel:x action:preview url:https://example.com/article",
        "channel:li action:preview url:https://example.com/article",
    ]
    
    for cmd_str in test_commands:
        cmd = processor.parse_command(cmd_str)
        print(f"   Input: {cmd_str}")
        if cmd.is_valid:
            print(f"   ✓ Valid command - Channel: {cmd.channel.value}, Action: {cmd.action.value}")
        else:
            print(f"   ❌ Invalid: {cmd.error_message}")
    
    # Test preview action (safe, doesn't actually post)
    print("\n3. Testing Preview Action (Safe)...")
    preview_cmd = processor.parse_command(
        "channel:x action:preview url:https://example.com/article"
    )
    
    if preview_cmd.is_valid:
        print("   Executing preview command...")
        result = await handler.execute_command(preview_cmd)
        
        if result.success:
            print(f"   ✓ Preview successful")
            print(f"   Channel: {result.channel}")
            print(f"   Content preview:")
            print(f"   ---")
            print(result.content[:200] + "..." if len(result.content) > 200 else result.content)
            print(f"   ---")
        else:
            print(f"   ❌ Preview failed: {result.error}")
    
    # Test results storage
    print("\n4. Testing Results Storage...")
    results_summary = handler.get_results_summary()
    print(results_summary)
    
    print("\n" + "=" * 70)
    print("Integration Tests Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_social_handler())
