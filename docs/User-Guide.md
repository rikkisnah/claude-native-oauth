# User Guide

`main.py` requires a positional prompt for request execution.

## Examples

```bash
uv run python main.py "Summarize this repository."
uv run python main.py --json "Return a short JSON-safe sentence."
uv run python main.py --stream "Stream a short answer."
uv run python main.py --repo /path/to/repo "Summarize this repository."
```

## Model selection

Aliases:

- `sonnet`
- `opus`
- `haiku`

You can also pass a full Anthropic model identifier with `--model`.

## Sampling parameters

```bash
uv run python main.py --top-p 0.95 "Creative writing prompt."
uv run python main.py --top-k 40 "List some facts."
uv run python main.py --stop-sequences DONE END "Write until stopped."
```

These flags are optional and omitted from the API payload when not provided.

## Scorecard

```bash
make score-repo
make validate
```

The repository scorecard is implemented locally in `scripts/score_repo.py`. It
does not require a second checkout or any out-of-repo scorer script.
Use `make validate` for the full repository gate: lint, tests, and scoring.

## Error handling

The client raises typed exceptions for API failures:

| Exception | Status Code |
|---|---|
| `BadRequestError` | 400 |
| `AuthenticationError` | 401 |
| `PermissionDeniedError` | 403 |
| `NotFoundError` | 404 |
| `RateLimitError` | 429 |
| `ServerError` | 5xx |

All exceptions inherit from `ClaudeAPIError` and expose a `status_code`
attribute. Requests that fail with 429 or 5xx are retried up to 3 times with
exponential backoff (1s, 2s, 4s). A 401 triggers an automatic token refresh
without consuming a retry slot.

Retry behavior is configurable via the `max_retries` and `retry_base_delay`
constructor parameters on `ClaudeNativeOAuthClient`.
