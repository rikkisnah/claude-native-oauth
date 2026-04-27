# ADR 006: Opus 4.7 Sampling Parameters

## Status

Accepted

## Context

The CLI exposes static model aliases through `MODEL_ALIASES`. Opus now resolves
to `claude-opus-4-7`, and Opus 4.7 does not accept `temperature`, `top_p`, or
`top_k` sampling parameters.

## Decision

The client omits sampling parameters by default and includes them only when
explicitly configured. It rejects `temperature`, `top_p`, and `top_k` locally
when the resolved model is `claude-opus-4-7`.

## Consequences

`--model opus` uses the current Opus alias without sending request fields that
would be rejected by the API. Callers that need sampling parameters must use a
model that supports them.
