# How It Works

`main.py` performs direct HTTP requests with `requests.post(...)`.

## Request flow

1. Read the Claude Code OAuth token from `~/.claude/.credentials.json`
2. Resolve the model alias if needed
3. Build Claude Code-compatible headers
4. Build the `system` block list, including the billing marker
5. Optionally include `top_p`, `top_k`, `stop_sequences`, and `metadata` in
   the payload when configured
6. `POST` to `https://api.anthropic.com/v1/messages?beta=true`
7. Parse server-sent events into a normalized response object

## Why the billing block matters

For Claude Code OAuth tokens, headers alone are not enough. The first system
block must include the billing marker or the direct request fails.

## Retry and error handling

The client maps HTTP status codes to typed Python exceptions rooted at
`ClaudeAPIError`. A flat hierarchy covers the most common failure modes: 400
(`BadRequestError`), 401 (`AuthenticationError`), 403
(`PermissionDeniedError`), 404 (`NotFoundError`), 429 (`RateLimitError`), and
5xx (`ServerError`).

When a request fails with 429 or 5xx, the client retries with exponential
backoff (`base_delay * 2^attempt`). The default is up to 3 retries with a 1s
base delay (1s, 2s, 4s). A 401 triggers a one-time token refresh via the
OAuth refresh endpoint, separate from the retry counter.
