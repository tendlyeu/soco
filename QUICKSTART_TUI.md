# Quick Start Guide - Tendly Social Media TUI

Get up and running with the Tendly Social Media Posting TUI in 5 minutes.

## 1. Installation (1 minute)

```bash
# Navigate to project directory
cd socode

# Install dependencies
pip install -r requirements.txt
```

## 2. Configuration (2 minutes)

```bash
# Copy the environment template
cp .env.sample .env

# Edit .env with your credentials
nano .env
```

Add your API keys:
```
ARCADE_API_KEY=your_key_here
XAI_API_KEY=your_key_here
ARCADE_USER_EMAIL=your_email@example.com
ARCADE_USER_PASSWORD=your_password
ARCADE_USER_ID=your_email@example.com
```

## 3. Run the TUI (1 minute)

```bash
python3 tui_main.py
```

You should see the welcome screen with the TUI interface.

## 4. Try Your First Command (1 minute)

### Preview Content (Safe - No Posting)
```
channel:x action:preview url:https://example.com/article
```

This generates a sample summary without actually posting.

### Post to X
```
channel:x action:summarise url:https://example.com/article
```

### Post to LinkedIn
```
channel:li action:summarise url:https://example.com/article
```

## Common Commands

| Command | Purpose |
|---------|---------|
| `help` | Show detailed help |
| `history` | Show recent commands |
| `clear` | Clear the output |
| `exit` | Exit the application |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+H` | Show help |
| `Ctrl+L` | Clear output |
| `q` | Quit |
| `Ctrl+C` | Quit |

## Command Syntax

```
channel:<channel> action:<action> url:<url> [content:"text"]
```

### Channels
- `x` or `twitter` - Post to X
- `li` or `linkedin` - Post to LinkedIn

### Actions
- `summarise` - AI summary from URL
- `post` - Post content directly
- `preview` - Preview without posting

## Example Workflow

```
# 1. Preview first (safe)
channel:x action:preview url:https://example.com/article

# 2. Review the output

# 3. Post to X
channel:x action:summarise url:https://example.com/article

# 4. Post to LinkedIn
channel:li action:summarise url:https://example.com/article

# 5. Check your posts
history
```

## Troubleshooting

**Q: "ARCADE_API_KEY must be provided"**
- A: Check your `.env` file exists and has the correct key

**Q: "Unknown channel"**
- A: Use `x`, `twitter`, `li`, or `linkedin`

**Q: "URL must start with http://"**
- A: Include the full URL with protocol: `https://example.com`

## Next Steps

- Read [TUI_README.md](TUI_README.md) for detailed documentation
- Check [test_tui.py](test_tui.py) for more examples
- Explore the [tui/](tui/) directory for component details

## Support

If you encounter issues:

1. Check the `.env` file is configured correctly
2. Verify API credentials are valid
3. Review error messages in the TUI output
4. Check the troubleshooting section in TUI_README.md

Happy posting! 🚀
