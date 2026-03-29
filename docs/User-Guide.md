# User Guide

`main.py` accepts either a positional prompt or stdin.

## Examples

```bash
uv run python main.py "Summarize this repository."
printf 'Say hello' | uv run python main.py
uv run python main.py --json "Return a short JSON-safe sentence."
uv run python main.py --stream "Stream a short answer."
```

## Model selection

Aliases:

- `sonnet`
- `opus`
- `haiku`

You can also pass a full Anthropic model identifier with `--model`.
