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
- [`.github/workflows/ci.yml`](./.github/workflows/ci.yml): GitHub Actions CI — runs `make check` and `make score-repo` on push and PR

## Documentation map

- [`INSTALL.md`](./INSTALL.md): a Codex-executable install and verification
  runbook with setup requirements, local install steps, and command examples
  for prompt execution, JSON output, streaming, token status, model selection,
  and repository-input mode
- [`CREATE-PR.md`](./CREATE-PR.md): a Codex-executable PR-preparation runbook
  with validation steps, release/version expectations, and the required PR
  checklist for this repository
- [`AGENTS.md`](./AGENTS.md): contributor rules for testing, coverage, scoring,
  and documentation updates

## Quick start

```bash
make install
make hello
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

For setup details, see [`INSTALL.md`](./INSTALL.md). For contribution and PR
workflow, see [`CREATE-PR.md`](./CREATE-PR.md). Both files are written as
actionable runbooks that Codex can execute directly.

## Disclaimer

> **This project likely violates Anthropic's Terms of Service and Acceptable
> Use Policy. Do not use, publish, or distribute it without reviewing those
> terms yourself.**

This repository is experimental code. It demonstrates a direct request flow
that reuses Claude Code OAuth credentials and request conventions outside of
Claude Code itself. Treat it as a research artifact, not a sanctioned
integration path.

### Policy concerns

| Concern | Severity | Detail |
|---|---|---|
| OAuth credential extraction | **High** | The token in `~/.claude/.credentials.json` is issued for Claude Code's own use. Extracting it and making raw HTTP calls outside of Claude Code is not an authorized use of that credential. |
| Billing header spoofing | **High** | The code sends `x-anthropic-billing-header: cc_version=2.1.81; cc_entrypoint=cli; cch=a9fc8;`, which makes Anthropic's backend attribute the request to Claude Code itself. |
| User-Agent impersonation | **High** | Requests use `User-Agent: claude-code/2.1.81` and `x-app: cli`, impersonating the official Claude Code client. |
| Token refresh via internal OAuth flow | **High** | The code refreshes tokens using Claude Code's OAuth client ID and scopes, extending unauthorized access beyond the original token lifetime. |
| Unauthorized beta flags | **Medium** | Headers such as `claude-code-20250219` and `oauth-2025-04-20` are internal beta features gated to Claude Code. |
| Safety header bypass | **Medium** | The code sets `anthropic-dangerous-direct-browser-access: true`, which is intended for specific approved contexts, not arbitrary third-party scripts. |

### Core issue

This client impersonates Claude Code to gain API access without a separate API
key. A Claude Pro or Max subscription gives access to Claude Code, but it does
not authorize extracting its credentials and building an independent client on
top of that auth flow.

### Recommended alternative

If you want supported programmatic access to Claude, use an Anthropic API key
from [console.anthropic.com](https://console.anthropic.com) and the official
[Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
instead.

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

`--token-status` prints human-readable `expires_at` and `seconds_remaining`
values in its JSON output.
