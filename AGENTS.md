# Repository Guidelines

## Project Structure & Module Organization

The production implementation lives in [`main.py`](./main.py). Keep the direct
Claude OAuth request path there. Tests live under [`tests/`](./tests), repo
automation helpers under [`scripts/`](./scripts), and contributor/runtime docs
under [`docs/`](./docs). The main entrypoints are:

- `main.py`: direct `POST /v1/messages?beta=true` client and CLI
- `scripts/score_repo.py`: wrapper for the external architecture scorecard
- `Makefile`: standard developer commands
- `~/.alias`: local shell shortcuts; keep the `cno` alias aligned with this repo

## Build, Test, and Development Commands

- `make`: show available targets
- `make install`: sync the `uv` environment with dev dependencies
- `make lint`: run `ruff` and `mypy`
- `make test`: run `pytest` with `100%` coverage gating
- `make check`: run lint and tests
- `make hello`: send a quick hello prompt to Claude
- `make score-repo`: run the external score wrapper
- `uv run python main.py "Say hello"`: run the client locally

## Error Handling

The client provides a typed exception hierarchy rooted at `ClaudeAPIError`.
Status codes map to `BadRequestError` (400), `AuthenticationError` (401),
`PermissionDeniedError` (403), `NotFoundError` (404), `RateLimitError` (429),
and `ServerError` (5xx). Requests that fail with 429 or 5xx are retried up to
3 times with exponential backoff. A 401 triggers an automatic token refresh
without consuming a retry slot.

## Coding Style & Naming Conventions

Use 4-space indentation and Python 3.11+ syntax. Prefer explicit types and
small dataclasses for structured values. Keep production logic in `main.py`
rather than moving core request behavior into helper packages. Use:

- `snake_case` for functions and variables
- `PascalCase` for dataclasses and client types
- short module docstrings at the top of each file

Formatting and static analysis are enforced with `ruff` and `mypy`.
All code paths and repository-facing behavior should be documented when they
change.

## Testing Guidelines

Tests use `pytest` and must keep total coverage at `100%`. Name files
`test_*.py` and keep test names descriptive, for example
`test_build_headers()` or `test_main_stream_output()`. Cover any changes to:

- request headers
- system blocks
- SSE parsing
- CLI flags and output modes

Run `make test` before opening a PR. Do not merge changes that reduce coverage
below `100%`.
Every code change must be followed by an appropriate test run. At minimum, run
the narrowest command that validates the change, and run `make check` for any
meaningful behavior change.
All test validation must finish at `100%` coverage.

## Documentation Rules

Every code change must include corresponding documentation updates in the same
commit. This is not optional — treat docs as part of the implementation, not a
follow-up task.

At minimum, review and update **all** of the following when making changes:

- `README.md` — quick start, CLI features, examples
- `INSTALL.md` — setup steps, verification commands
- `CREATE-PR.md` — PR checklist and workflow
- `AGENTS.md` and `CLAUDE.md` — contributor rules and build targets
- `docs/User-Guide.md` — end-user usage instructions
- `docs/How-It-Works.md` — architectural and implementation details
- `docs/adr/` — add or update Architecture Decision Records when introducing
  new design choices or changing existing ones
- any local alias entry in `~/.alias` that points at this repository

If a change adds, removes, or renames a Makefile target, CLI flag, dataclass,
public function, or configuration constant, every doc file above must be
checked and updated to reflect the new state. Do not assume a doc is
unaffected — open it and verify.

## Commit & Pull Request Guidelines

The repository is still new, so use short imperative commit messages such as
`Add JSON output test` or `Tighten OAuth payload validation`. Pull requests
should include:

- a brief summary of the change
- validation results from `make check` and `make score-repo`
- notes on any changes to the OAuth request contract
- confirmation that documentation was updated
- confirmation that test coverage remains at `100%`
- confirmation that the change was tested after implementation
- confirmation that the score output remains `10.0/10`

## Continuous Integration

A GitHub Actions workflow at `.github/workflows/ci.yml` runs on every push to
`main` and on every pull request targeting `main`. It executes `make check`
(lint + 100% coverage tests) and `make score-repo` (architecture scorecard).
All checks must pass before merging.

## Security & Configuration Tips

Do not commit tokens or credential files. The client reads the Claude Code
OAuth token from `~/.claude/.credentials.json`. Treat the billing header,
OAuth headers, and direct API contract as production behavior, not incidental
implementation details.
