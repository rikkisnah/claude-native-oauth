# Create PR

This file is a command runbook. It should show the exact commands to run for PR
preparation, including the `git add ...` and `git commit ...` commands, but it
should not assume Codex will execute those commands on your behalf unless you
explicitly ask for that.

## Before opening a PR

Run:

```bash
make validate
```

If `make validate` fails, stop. Do not proceed to staging, commit commands, or
PR preparation until the failure is fixed and `make validate` passes.

`make validate` includes both `make check` and `make score-repo`. If the score
drops below `10.0/10`, stop. Do not proceed until the score is restored.

`make score-repo` must remain self-contained. Do not introduce PR changes that
make it depend on files, scripts, or checkouts outside this repository.

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

Show a `git add ...` command for the files that belong to the change before
committing so the user can run it manually.

Do not stop after asking the version question. After the user answers, always
provide the exact `git add ...` command that stages the changed files for this
branch.

```bash
git add main.py tests README.md INSTALL.md CREATE-PR.md AGENTS.md Makefile pyproject.toml .gitignore
```

Use a narrower `git add ...` command when the change touches fewer files.

For a docs-only change in this file, that means showing:

```bash
git add CREATE-PR.md
```

## Commit commands

Use a short imperative subject. Always give the user the exact commit command
to run manually. A one-line commit command looks like:

```bash
git commit -m "Tighten README disclaimer"
```

When details matter, provide a subject-plus-body command like:

```bash
git commit -m "Tighten README disclaimer" -m "Clarify that the repository is experimental code." -m "Document the likely OAuth, billing-header, beta-flag, and policy risks."
```

Do not create the commit automatically when following this file unless the user
explicitly asks for execution. The default expectation is to present the exact
commands for the user to run manually.

After the version answer is known, present the commands in this order:

1. `git add ...`
2. `git commit ...`
3. the suggested PR title and PR body

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
- `make validate`
```
