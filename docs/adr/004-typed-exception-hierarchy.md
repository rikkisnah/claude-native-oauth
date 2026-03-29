# ADR 004: Typed exception hierarchy for API errors

## Status

Accepted

## Decision

Map HTTP status codes to typed Python exception subclasses rooted at
`ClaudeAPIError`. Use a flat hierarchy with one class per significant
status code (400, 401, 403, 404, 429) and a catch-all `ServerError`
for 5xx responses.

## Rationale

Callers need to handle rate limits, authentication failures, and
server errors differently. A typed hierarchy lets them catch specific
exceptions rather than inspecting HTTP status codes. The mapping
approach keeps the `_post` method clean and makes retry decisions
straightforward.
