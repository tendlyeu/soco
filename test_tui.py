#!/usr/bin/env python3
"""Test script for TUI components."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from tui.components.command_processor import CommandProcessor, Channel, Action


def test_command_parsing():
    """Test command parsing functionality."""
    processor = CommandProcessor()
    
    test_cases = [
        {
            "input": "channel:x action:summarise url:https://example.com",
            "expected_channel": Channel.X,
            "expected_action": Action.SUMMARISE,
            "expected_url": "https://example.com",
            "should_be_valid": True
        },
        {
            "input": "channel:li action:post url:https://example.com content:\"Check this out!\"",
            "expected_channel": Channel.LINKEDIN,
            "expected_action": Action.POST,
            "expected_url": "https://example.com",
            "expected_content": "Check this out!",
            "should_be_valid": True
        },
        {
            "input": "channel:twitter action:preview url:https://example.com",
            "expected_channel": Channel.TWITTER,
            "expected_action": Action.PREVIEW,
            "expected_url": "https://example.com",
            "should_be_valid": True
        },
        {
            "input": "channel:x action:summarise",
            "should_be_valid": False,
            "expected_error": "URL required"
        },
        {
            "input": "channel:invalid action:summarise url:https://example.com",
            "should_be_valid": False,
            "expected_error": "Unknown channel"
        },
    ]
    
    print("=" * 70)
    print("Testing Command Parser")
    print("=" * 70)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['input']}")
        cmd = processor.parse_command(test["input"])
        
        # Check validity
        if cmd.is_valid != test["should_be_valid"]:
            print(f"  ❌ FAILED: Expected valid={test['should_be_valid']}, got {cmd.is_valid}")
            if cmd.error_message:
                print(f"     Error: {cmd.error_message}")
            continue
        
        if not test["should_be_valid"]:
            if test.get("expected_error") and test["expected_error"] in cmd.error_message:
                print(f"  ✓ PASSED: Got expected error")
            else:
                print(f"  ❌ FAILED: Expected error containing '{test.get('expected_error')}', got '{cmd.error_message}'")
            continue
        
        # Check parsed values
        all_correct = True
        
        if test.get("expected_channel") and cmd.channel != test["expected_channel"]:
            print(f"  ❌ Channel mismatch: expected {test['expected_channel']}, got {cmd.channel}")
            all_correct = False
        
        if test.get("expected_action") and cmd.action != test["expected_action"]:
            print(f"  ❌ Action mismatch: expected {test['expected_action']}, got {cmd.action}")
            all_correct = False
        
        if test.get("expected_url") and cmd.url != test["expected_url"]:
            print(f"  ❌ URL mismatch: expected {test['expected_url']}, got {cmd.url}")
            all_correct = False
        
        if test.get("expected_content") and cmd.content != test["expected_content"]:
            print(f"  ❌ Content mismatch: expected {test['expected_content']}, got {cmd.content}")
            all_correct = False
        
        if all_correct:
            print(f"  ✓ PASSED")
    
    print("\n" + "=" * 70)
    print("Command Parser Tests Complete")
    print("=" * 70)


def test_help_text():
    """Test help text generation."""
    processor = CommandProcessor()
    help_text = processor.get_help()
    
    print("\n" + "=" * 70)
    print("Help Text")
    print("=" * 70)
    print(help_text)


if __name__ == "__main__":
    test_command_parsing()
    test_help_text()
