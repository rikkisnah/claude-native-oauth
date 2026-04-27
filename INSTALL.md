# Install

This file is an executable runbook. Codex should follow it directly when asked
to install, verify, or smoke-test this repository locally.

## Requirements

- Python 3.11+
- `uv`
- A working Claude Code login on the machine
- `~/.claude/.credentials.json` containing `claudeAiOauth.accessToken`

## Setup

```bash
make install
make validate
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

The status output prints `expires_at` as a human-readable UTC timestamp and
`seconds_remaining` as a readable duration.

## Supported models

```bash
uv run python main.py --list-models
uv run python main.py --model opus "Explain the tradeoffs."
```

The built-in aliases resolve to `claude-sonnet-4-6`, `claude-opus-4-7`, and
`claude-haiku-4-5-20251001`. Sampling parameters are optional. Do not combine
`--model opus` with `--temperature`, `--top-p`, or `--top-k`; the CLI rejects
those parameters locally for Opus 4.7.

## Sampling parameters

```bash
uv run python main.py --top-p 0.95 "Explain quantum computing."
uv run python main.py --top-k 40 "List three facts."
uv run python main.py --stop-sequences DONE "Write until done."
```

## Scorecard

```bash
make score-repo
make validate
```

The scorecard is implemented entirely in `scripts/score_repo.py`. It does not
read tools, scripts, or source files from another repository.
Use `make validate` when you want the full repository gate: lint, tests, and
scoring.

## Read a repository into the prompt

```bash
uv run python main.py --repo /path/to/repo "Summarize the architecture."
```
