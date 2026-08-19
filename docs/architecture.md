# Architecture

## Context

The source application is a strong single-user, local-first Starlette/SQLite reader. This edition
changes the trust boundary: it accepts Internet-facing authenticated users, stores documents in an
object service, and optionally spends money through a model provider. The cloud edition therefore
uses a separate repository and data model rather than adding flags to the private application.

## Runtime components

```text
Browser / installed PWA
        |
        v
FastAPI web process ---- PostgreSQL
        |                    ^
        v                    |
S3-compatible storage <--- Worker ---- AnalysisProvider ---- OpenAI (optional)
```

The web process handles sessions, tenant-scoped HTML/API routes, upload validation, and job
creation. The worker claims jobs from PostgreSQL using leases and `FOR UPDATE SKIP LOCKED`, reads
only server-generated object keys, creates bounded PDF batches, validates provider results, and
commits each page idempotently.

## Layers

- `config`: validated settings with safe development defaults.
- `db`: SQLAlchemy models, sessions, migrations, and tenant-scoped repositories.
- `domain`: immutable request/result models and policy checks.
- `storage`: S3-compatible production adapter and in-memory test adapter.
- `analysis`: provider protocol, fake/disabled/OpenAI implementations, schema and prompt versions.
- `jobs`: state machine, leasing, batching, retry, cancellation, and usage accounting.
- `services`: authenticated use cases; the only layer called by web handlers and workers.
- `web`: server-rendered pages, JSON endpoints, CSP/CSRF/session middleware, PWA assets.

## Data ownership

`tenant_id` is present on every business aggregate even when ownership is derivable through joins.
Unique constraints include `tenant_id`; repositories require it explicitly. Users are linked to
tenants by memberships so future team plans do not require replacing the ownership model.

Object keys follow a server-owned pattern such as:

```text
tenants/{tenant_uuid}/documents/{document_uuid}/source.pdf
tenants/{tenant_uuid}/documents/{document_uuid}/pages/{page}.png
```

Clients never submit or receive raw storage credentials. Downloads are streamed after a database
ownership check rather than exposing arbitrary keys.

## Job state machine

```text
queued -> running -> completed
   |        |  \-> partial
   |        \----> failed -> queued (bounded retry)
   \--------------> cancelled
```

Running jobs carry a lease owner, lease expiry, heartbeat, attempt count, next page, cancellation
request, and bounded error summary. Expired leases are reclaimable. Completed page batches remain
committed, making retries partial and idempotent rather than all-or-nothing.

## Provider data flow

1. Split the registered PDF into configurable small page ranges while preserving original pages.
2. Send the batch as a PDF `input_file` from the worker with configured `detail`.
3. Ask for a Pydantic model matching the versioned page-analysis schema.
4. Handle refusal, timeout, rate limit, incomplete output, and schema failure as typed errors.
5. Independently validate the parsed model and page range before persistence.
6. Store response identifiers, token usage, latency, provider/model/prompt/schema versions, but not
   hidden reasoning or provider credentials.

## Search

PostgreSQL is authoritative. v1 combines tenant-filtered full-text search with bounded `ILIKE`
fallback for CJK substrings. Search rows are derived from PDF text, analyses, notes, terms, and
formulas. Ranking improvements can be added without changing ownership rules.

## Security posture

- Argon2id password hashing and signed, HttpOnly, SameSite session cookies.
- Origin/CSRF checks on all browser state changes; secure cookies in production.
- Strict CSP with bundled static assets and no third-party CDN.
- Upload byte/page limits, PDF signature and parser validation, sanitized display filenames.
- Tenant filters at repository boundaries plus adversarial two-tenant tests.
- Structured logs with allowlisted metadata; document text and secrets are excluded.
- Provider concurrency, retry, page, byte, and output-token limits protect spend.

## Alternatives

See `docs/adr/` for decisions on repository separation, PostgreSQL/object storage, database-backed
jobs, and provider isolation.

