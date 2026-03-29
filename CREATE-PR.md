# Create PR

This file is a command runbook. It should show the exact commands to run for PR
preparation, but it should not assume Codex will create the commit on your
behalf unless you explicitly ask for that.

## Before opening a PR

Run:

```bash
make check
make score-repo
```

If `make check` fails, stop. Do not proceed to staging, commit commands, or PR
preparation until the failure is fixed and `make check` passes.

If `make score-repo` fails or drops below `10.0/10`, stop. Do not proceed until
the score is restored.

## Version prompt

Before showing commit commands, ask whether the version should be increased.

Use a direct prompt such as:

```text
Do you want to bump the version for this change?
```

If the change affects shipped behavior, CLI surface, or release-visible
functionality, recommend a version bump. If the user wants a version bump,
update the version before staging and committing.

## Stage files

Run a `git add ...` command for the files that belong to the change before
committing.

```bash
git add main.py tests README.md INSTALL.md CREATE-PR.md AGENTS.md Makefile pyproject.toml .gitignore
```

Use a narrower `git add ...` command when the change touches fewer files.

## Commit commands

Use a short imperative subject. Copy and run a one-line commit command like:

```bash
git commit -m "Tighten README disclaimer"
```

When details matter, copy and run a subject-plus-body command like:

```bash
git commit -m "Tighten README disclaimer" -m "Clarify that the repository is experimental code." -m "Document the likely OAuth, billing-header, beta-flag, and policy risks."
```

Do not create the commit automatically when following this file unless the user
explicitly asks for execution. The default expectation is to present the
commands for the user to run.

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
