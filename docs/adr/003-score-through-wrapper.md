# ADR 003: Keep repository scoring self-contained

## Status

Accepted

## Decision

The repository remains independent while `scripts/score_repo.py` evaluates the
repo directly with in-repo score logic.

## Rationale

The earlier score flow depended on an out-of-repo scorer and leaked
machine-specific assumptions into this project. The current scorecard keeps the
check reproducible in CI while ensuring every required scoring dependency lives
inside this repository.
