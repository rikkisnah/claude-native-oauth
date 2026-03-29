# Install

## Requirements

- Python 3.11+
- `uv`
- A working Claude Code login on the machine
- `~/.claude/.credentials.json` containing `claudeAiOauth.accessToken`

## Setup

```bash
make install
```

## Verify

```bash
uv run python main.py "Say hello in five words"
```

If you run `uv run python main.py` without a positional prompt, it will fail
fast with an error instead of waiting on stdin.

## JSON output

```bash
uv run python main.py --json "Return exactly one sentence."
```

## Streaming output

```bash
uv run python main.py --stream "Explain direct OAuth message streaming."
```

## Token status

```bash
uv run python main.py --token-status
```

## Supported models

```bash
uv run python main.py --list-models
uv run python main.py --model opus "Explain the tradeoffs."
```

## Read a repository into the prompt

```bash
uv run python main.py --repo /path/to/repo "Summarize the architecture."
```
