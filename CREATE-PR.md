# Create PR

## Before opening a PR

Run:

```bash
make check
make score-repo
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
