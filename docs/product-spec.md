# Product specification

## Outcome

MFE Study Cloud v1.0 is a self-hosted, multi-user PWA that turns uploaded course PDFs into a
page-aligned study experience. A server-side worker can generate bilingual explanations through a
configured analysis provider; the default fake provider supports a zero-cost offline demo.

## Primary journey

1. A user registers and receives a private personal tenant.
2. The user creates a course and chapter.
3. The user uploads a bounded, readable PDF.
4. The server stores it under a generated tenant/document object key and records its SHA-256.
5. The user starts an analysis job and can inspect progress, failures, retries, or cancellation.
6. A worker splits the PDF into small page batches and invokes the configured provider.
7. Versioned structured output is validated before transactional persistence.
8. The user reads original pages beside Chinese explanations, formulas, terms, and notes.
9. Search and reading progress remain strictly scoped to the authenticated tenant.

## v1 scope

- Registration, login, logout, session hardening, and CSRF.
- Personal tenant creation and tenant-scoped queries.
- Courses, chapters, PDF documents, analysis jobs, notes, search, and reading progress.
- Page-aligned PDF rendering and structured analysis display.
- Fake, disabled, and OpenAI analysis providers.
- PostgreSQL, S3-compatible object storage, database-leased worker, Docker Compose, and PWA.
- Health checks, structured logs, backup/restore and production deployment guidance.

## Explicitly later

- Payments, subscriptions, social feeds, collaborative editing, email marketing, and app-store
  packaging are not v1 release gates.
- Per-user browser entry of provider keys is intentionally excluded. Server administrator BYOK is
  the only v1 real-provider mode.
- MCP and the private application's CLI are deferred unless required for release operations.

## Product invariants

- A tenant cannot enumerate, infer, download, search, update, or delete another tenant's data.
- A client supplies identifiers, never storage paths or object keys.
- A page analysis is admitted only after schema validation and document/page ownership checks.
- Job retries are idempotent by document hash, page range, provider, model, prompt version, and
  schema version.
- Missing provider configuration never prevents the web application from starting.
- Service-worker caching never includes authenticated HTML, API responses, PDFs, or analysis data.

## Release success

The release candidate is successful when a new contributor can follow the README, start the full
container stack, register two isolated users, run a fake analysis without network access, install
the PWA, and pass the documented quality/security gates.

