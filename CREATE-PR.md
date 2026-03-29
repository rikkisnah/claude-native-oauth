# Create PR

This file is an executable runbook. Codex should follow it directly when asked
to prepare a change for review or validate PR readiness.

## Before opening a PR

Run:

```bash
make check
make score-repo
```

## Stage files

Add the files that belong to the change before committing.

```bash
git add main.py tests README.md INSTALL.md CREATE-PR.md AGENTS.md Makefile pyproject.toml .gitignore
```

Use a narrower `git add ...` command when the change touches fewer files.

## Commit commands

Use a short imperative subject. A one-line commit command looks like:

```bash
git commit -m "Tighten README disclaimer"
```

When details matter, use a subject plus body:

```bash
git commit -m "Tighten README disclaimer" -m "Clarify that the repository is experimental code." -m "Document the likely OAuth, billing-header, beta-flag, and policy risks."
```

## PR checklist

- Keep the direct OAuth contract intact
- Preserve the billing header block in `main.py`
- Add or update tests for payload or stream parsing changes
- Update docs when flags or request behavior change
- Update the version when the change affects shipped behavior, CLI surface, or release-visible functionality

## Suggested PR body

```md
## Summary
- ...

## Version
- Updated to `x.y.z`

## Validation
- `make check`
- `make score-repo`
```
