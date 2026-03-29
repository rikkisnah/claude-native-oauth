# ADR 005: Configurable retries with exponential backoff

## Status

Accepted

## Decision

The client retries requests on 429 and 5xx responses with exponential
backoff. Retry count and base delay are configurable via constructor
parameters. The existing 401 token-refresh path remains separate from
the retry counter.

## Rationale

Rate limits and transient server errors are common in production API
usage. Built-in retries with backoff reduce the burden on callers
while remaining opt-out (set `max_retries=0` to disable). Keeping 401
refresh separate ensures token expiry does not consume retry budget.
