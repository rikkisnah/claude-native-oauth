# How It Works

`main.py` performs direct HTTP requests with `requests.post(...)`.

## Request flow

1. Read the Claude Code OAuth token from `~/.claude/.credentials.json`
2. Resolve the model alias if needed
3. Validate model-specific payload constraints, including Opus 4.7 sampling
   parameter restrictions
4. Build Claude Code-compatible headers
5. Build the `system` block list, including the billing marker
6. Optionally include `temperature`, `top_p`, `top_k`, `stop_sequences`, and
   `metadata` in the payload when configured
7. `POST` to `https://api.anthropic.com/v1/messages?beta=true`
8. Parse server-sent events into a normalized response object

Model aliases are static constants in `main.py`: `sonnet` maps to
`claude-sonnet-4-6`, `opus` maps to `claude-opus-4-7`, and `haiku` maps to
`claude-haiku-4-5-20251001`. Run `uv run python main.py --list-models` to
inspect the active alias table in this checkout.

## Repository-local scoring

`make score-repo` runs `scripts/score_repo.py`, which is implemented entirely
inside this repository. The scoring check must remain self-contained and must
not load code, scripts, or score logic from another checkout.
`make validate` runs the full repository gate by chaining `make check` and
`make score-repo`.

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
