# Security policy

## Supported versions

Only the latest release candidate or stable release receives security fixes during the initial
project phase.

## Reporting a vulnerability

Do not open a public issue containing a credential, private document, exploit payload, or user
data. Until a private security mailbox is published, contact the repository owner privately and
include only the minimum reproduction details.

## Security boundaries

- Provider credentials are server/worker secrets and are never browser configuration.
- Every business query is explicitly tenant scoped.
- Object keys are server generated and never accepted directly from clients.
- Uploads are size-bounded and verified as readable PDFs before persistence or analysis.
- Browser state changes require an authenticated session and CSRF token.
- Logs redact credentials, session values, raw provider payloads, and document content.

Please see `docs/threat-model.md` for the release threat model and verification matrix.

