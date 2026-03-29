# ADR 003: Use a score wrapper for external architecture scoring

## Status

Accepted

## Decision

The repository remains independent while `scripts/score_repo.py` projects it
into the shape expected by the external scorecard.

## Rationale

The external score script assumes a repository layout that does not match this
project. A wrapper keeps the repo independent while still using the scoring
system in a repeatable way.
