# claude-native-oauth

`claude-native-oauth` is a direct Anthropic Messages API client that uses the
Claude Code OAuth token stored in `~/.claude/.credentials.json`.

It does not shell out to the Claude CLI. It performs a real
`POST /v1/messages?beta=true` request with the same OAuth-specific request
contract Claude Code expects:

- `Authorization: Bearer <oauth token>`
- `anthropic-beta: prompt-caching-2024-07-31,claude-code-20250219,oauth-2025-04-20`
- `anthropic-dangerous-direct-browser-access: true`
- `x-app: cli`
- the billing marker in the first `system` block

## What is in this repo

- [`main.py`](./main.py): the production implementation and CLI entrypoint
- [`Makefile`](./Makefile): `uv`-based install, lint, test, and score targets
- [`scripts/score_repo.py`](./scripts/score_repo.py): local wrapper around the external architecture scorecard
- [`tests`](./tests): unit tests for request construction, stream parsing, and CLI behavior

## Quick start

```bash
make install
uv run python main.py "Say hello in five words"
make smoke-endpoint
uv run python main.py --token-status
uv run python main.py --list-models
uv run python main.py --repo /path/to/repo "Summarize this codebase"
```

Optional local shell alias:

```bash
alias cno='uv run --project /mnt/data/src/rikkisnah/claude-native-oauth python /mnt/data/src/rikkisnah/claude-native-oauth/main.py'
```

Then use:

```bash
cno --token-status
cno "Say hello in five words"
```

`main.py` now requires a positional prompt argument for request execution. It
does not implicitly block on stdin when no prompt is provided.

For installation details, see [`INSTALL.md`](./INSTALL.md).

## Disclaimer

This repository is experimental code. It demonstrates a direct request flow
that reuses Claude Code OAuth credentials and request conventions outside of
Claude Code itself. Treat it as a research artifact, not a sanctioned
integration path.

Likely concerns include:

- OAuth token misuse: the token in `~/.claude/.credentials.json` is issued for
  Claude Code's own use. Extracting it and making raw HTTP calls outside of
  Claude Code is likely not an authorized use of that credential.
- Spoofed billing headers: the code sends
  `x-anthropic-billing-header: cc_version=2.1.81; cc_entrypoint=cli; cch=a9fc8;`,
  which makes Anthropic's backend think the request is coming from Claude Code
  itself.
- Unauthorized beta flags: headers such as `claude-code-20250219` and
  `oauth-2025-04-20` appear to be internal beta features gated to Claude Code.
- Safety guardrail bypass: the code sets
  `anthropic-dangerous-direct-browser-access: true`, which appears intended for
  specific approved contexts rather than arbitrary third-party scripts.

The core issue is that this client can look like it is impersonating Claude
Code to gain API access without using a separate API key. A Claude Pro or Max
subscription gives access to Claude Code, but it does not necessarily authorize
extracting its credentials and building an independent client on top of that
auth flow.

If you want supported programmatic access to Claude, use an Anthropic API key
from `console.anthropic.com` and the official Anthropic SDK instead.

Use or distribution of this code may violate Anthropic's Terms of Service or
Acceptable Use Policy. Review those terms yourself before using, sharing, or
publishing this project.

## Why this exists

The public Anthropic API documentation does not describe the full request
contract needed for Claude Code OAuth tokens. This project packages that
contract into a single audited Python module so you can call the endpoint
directly without routing through the Claude binary.

## CLI features

- `--token-status`: inspect local OAuth token expiry and refresh state
- `--list-models`: show supported model aliases
- `--model <name>`: pick the model used for a prompt
- `--repo <path>`: read a repository snapshot into the prompt for codebase analysis
