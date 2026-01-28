# Tendly Social Media Posting TUI

A modern terminal user interface (TUI) for automating social media posting to X (Twitter) and LinkedIn using AI-powered content summarization.

## Overview

The Tendly Social Media Posting TUI provides a command-line interface for:

- **Summarizing content** from URLs using XAI (Grok) API
- **Posting to X (Twitter)** with automatic formatting
- **Posting to LinkedIn** with professional content
- **Previewing content** before posting
- **Managing posting history** and results

Built with [Textual](https://textual.textualize.io/) for a rich terminal experience and inspired by the [FinCode](https://github.com/predictivelabsai/fincode) project architecture.

## Features

### Command Syntax

The TUI uses a simple key:value command syntax:

```
channel:<channel> action:<action> url:<url> [content:"text"]
```

### Supported Channels

- **`x` or `twitter`** - Post to X (formerly Twitter)
- **`li` or `linkedin`** - Post to LinkedIn

### Supported Actions

- **`summarise`** - Generate AI summary from URL and post automatically
- **`post`** - Post content directly to the channel
- **`preview`** - Preview content before posting (safe, no actual posting)

### Example Commands

#### 1. Summarize and post to X
```
channel:x action:summarise url:https://example.com/article
```

#### 2. Post to LinkedIn with custom content
```
channel:li action:post url:https://example.com content:"Check this out!"
```

#### 3. Preview before posting to Twitter
```
channel:twitter action:preview url:https://example.com
```

#### 4. Post directly to LinkedIn
```
channel:linkedin action:post content:"Great opportunity!" url:https://example.com
```

## Installation

### Prerequisites

- Python 3.8+
- API credentials for Arcade AI and XAI (Grok)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/tendlyeu/socode.git
   cd socode
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.sample .env
   ```

4. **Fill in your credentials in `.env`**
   ```
   ARCADE_API_KEY=your_arcade_api_key
   XAI_API_KEY=your_xai_api_key
   ARCADE_USER_EMAIL=your_email@example.com
   ARCADE_USER_PASSWORD=your_password
   ARCADE_USER_ID=your_email@example.com
   ```

## Running the TUI

### Start the application
```bash
python3 tui_main.py
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+H` | Show help |
| `Ctrl+L` | Clear output |
| `q` | Quit application |
| `Ctrl+C` | Quit application |

### Built-in Commands

- **`help`** - Display command syntax and examples
- **`history`** - Show recent command history (last 10)
- **`clear`** - Clear the output panel
- **`exit`** or **`quit`** - Exit the application

## Project Structure

```
socode/
├── tui/
│   ├── __init__.py
│   ├── app.py                          # Main Textual TUI application
│   └── components/
│       ├── __init__.py
│       ├── command_processor.py        # Command parsing logic
│       └── social_handler.py           # Social media posting handler
├── tui_main.py                         # Entry point for TUI
├── utils/
│   ├── social_poster.py               # Arcade API integration
│   └── summarizer.py                  # XAI summarization
├── .env.sample                         # Environment template
├── .env                                # Actual credentials (not committed)
├── requirements.txt                    # Python dependencies
└── TUI_README.md                       # This file
```

## Component Details

### Command Processor (`tui/components/command_processor.py`)

Handles parsing of user input into structured commands:

- Parses key:value pairs from user input
- Validates command structure
- Supports quoted values for content with spaces
- Maintains command history
- Provides help text

**Key Classes:**
- `CommandProcessor` - Main parser
- `Command` - Data class for parsed commands
- `Channel` - Enum for supported channels
- `Action` - Enum for supported actions

### Social Handler (`tui/components/social_handler.py`)

Manages social media posting operations:

- Initializes API clients (Arcade, XAI)
- Executes commands (summarise, post, preview)
- Handles API responses
- Saves posting results to JSON files
- Provides result summaries

**Key Classes:**
- `SocialMediaHandler` - Main handler
- `PostResult` - Data class for posting results

### Main TUI App (`tui/app.py`)

Textual application with rich terminal UI:

- Command input with autocomplete suggestions
- Rich output formatting with colors
- Status bar showing current state
- Welcome message with quick examples
- Keyboard shortcuts for common actions

**Key Components:**
- `SocialMediaTUI` - Main Textual app
- `StatusPanel` - Status display widget
- `OutputPanel` - Result display widget

## API Integration

### Arcade AI

Used for posting to social media platforms:

- **Endpoint:** `https://api.arcade.dev/v1/tools/execute`
- **Tools:** `X.PostTweet`, `LinkedIn.CreatePost`
- **Authentication:** API key in Authorization header

### XAI (Grok)

Used for content summarization:

- **Endpoint:** `https://api.x.ai/v1`
- **Models:** `grok-3`, `grok-4-fast-reasoning`
- **Use:** Generate platform-specific summaries

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ARCADE_API_KEY` | Arcade AI API key | Yes |
| `XAI_API_KEY` | XAI (Grok) API key | Yes |
| `XAI_MODEL` | XAI model to use | No (default: grok-3) |
| `ARCADE_USER_EMAIL` | Arcade account email | Yes |
| `ARCADE_USER_PASSWORD` | Arcade account password | Yes |
| `ARCADE_USER_ID` | Arcade user ID | Yes |
| `LINKEDIN_PAGE` | LinkedIn company page URL | No |
| `POST_DELAY` | Delay between posts (seconds) | No (default: 5) |
| `DEBUG` | Enable debug logging | No (default: false) |

## Testing

### Unit Tests

Test command parsing:
```bash
python3 test_tui.py
```

### Integration Tests

Test with actual API credentials:
```bash
python3 test_integration.py
```

## Workflow Example

1. **Start the TUI**
   ```bash
   python3 tui_main.py
   ```

2. **Preview content first**
   ```
   channel:x action:preview url:https://example.com/article
   ```

3. **Review the generated summary**

4. **Post to X**
   ```
   channel:x action:summarise url:https://example.com/article
   ```

5. **Post to LinkedIn**
   ```
   channel:li action:summarise url:https://example.com/article
   ```

6. **Check history**
   ```
   history
   ```

## Error Handling

The TUI provides clear error messages for:

- Missing required fields
- Invalid channels or actions
- Malformed URLs
- API failures
- Configuration issues

All errors are displayed in the output panel with red highlighting.

## Results Storage

Posting results are automatically saved to `post_results/` directory as JSON files with:

- Success/failure status
- Channel information
- Posted content
- Post URL (if available)
- Timestamp
- Error messages (if any)

## Troubleshooting

### "ARCADE_API_KEY must be provided"
- Ensure `.env` file exists in the socode directory
- Check that `ARCADE_API_KEY` is set correctly
- Verify the key is valid and not expired

### "XAI_API_KEY must be provided"
- Check `.env` file for `XAI_API_KEY`
- Verify the key is valid and has proper permissions

### "Command Error: Unknown channel"
- Use valid channel names: `x`, `twitter`, `li`, or `linkedin`
- Check for typos in the command

### "URL must start with http:// or https://"
- Ensure URLs are complete with protocol
- Example: `https://example.com` not `example.com`

### Preview works but posting fails
- Check API credentials are valid
- Verify Arcade user account has posting permissions
- Check rate limiting - wait a few seconds before retrying

## Architecture Inspiration

This TUI is inspired by the excellent [FinCode](https://github.com/predictivelabsai/fincode) project, which demonstrates:

- Command-based CLI interface with Textual
- Rich terminal output formatting
- Async command processing
- Component-based architecture

## Future Enhancements

- [ ] Support for additional platforms (Facebook, Instagram)
- [ ] Scheduled posting
- [ ] Content templates and presets
- [ ] Multi-URL batch processing
- [ ] Analytics and engagement tracking
- [ ] Content editing before posting
- [ ] Hashtag suggestions
- [ ] Image/media attachment support
- [ ] Team collaboration features

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

See LICENSE file in the repository.

## Support

For issues, questions, or suggestions:

1. Check the troubleshooting section above
2. Review existing GitHub issues
3. Create a new issue with detailed information
4. Contact the development team

## Related Resources

- [Textual Documentation](https://textual.textualize.io/)
- [Arcade AI Documentation](https://arcade.dev/)
- [XAI Documentation](https://console.x.ai/)
- [FinCode Project](https://github.com/predictivelabsai/fincode)
