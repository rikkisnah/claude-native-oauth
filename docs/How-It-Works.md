# How It Works

`main.py` performs direct HTTP requests with `requests.post(...)`.

## Request flow

1. Read the Claude Code OAuth token from `~/.claude/.credentials.json`
2. Resolve the model alias if needed
3. Build Claude Code-compatible headers
4. Build the `system` block list, including the billing marker
5. `POST` to `https://api.anthropic.com/v1/messages?beta=true`
6. Parse server-sent events into a normalized response object

## Why the billing block matters

For Claude Code OAuth tokens, headers alone are not enough. The first system
block must include the billing marker or the direct request fails.
