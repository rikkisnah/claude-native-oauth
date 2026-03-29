# ADR 001: Use direct HTTP POST instead of the Claude CLI

## Status

Accepted

## Decision

The production path sends direct HTTP requests to Anthropic with `requests`.

## Rationale

The repository exists to make the direct OAuth request contract explicit and
testable. Wrapping the Claude CLI would hide that contract and make the project
less useful as a reference implementation.
