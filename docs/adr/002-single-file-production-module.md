# ADR 002: Keep the production implementation in main.py

## Status

Accepted

## Decision

The repository keeps the production request logic in a single root-level
`main.py`.

## Rationale

The user requirement is to keep the implementation focused on one auditable
entrypoint. Supporting scripts and tests may exist, but the production request
path stays in `main.py`.
