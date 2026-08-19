# ADR 0003: Server-side AnalysisProvider boundary

- Status: accepted

## Decision

All model use runs behind an `AnalysisProvider` protocol in the worker. Ship fake, disabled, and
OpenAI Responses implementations. Configuration selects the provider; browser requests cannot
select credentials, endpoints, or arbitrary models.

## Why

This keeps CI free, makes missing credentials non-fatal, centralizes paid-call limits and redaction,
and prevents provider details from leaking through UI code. Pydantic structured outputs mirror a
versioned public JSON schema and are validated again before persistence.

## Consequences

Provider-specific response metadata is normalized into a small audit record. New providers must
pass the same contract, idempotency, refusal, and schema tests.

