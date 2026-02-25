# CLAUDE.md

## Security Rules

- **NEVER commit API keys, passwords, or secrets** to any file in the repo — not in code, not in docs, not in markdown examples.
- Always use placeholder values (e.g., `your_xai_key`) in documentation and examples.
- Real credentials belong ONLY in `.env` (which is gitignored).
- Before committing, scan staged changes for patterns like `xai-`, `arc_proj`, passwords, or any string that looks like a real credential.
