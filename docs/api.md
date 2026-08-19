# HTTP API and provider boundary

The canonical OpenAPI document is served at `/api/openapi.json`. Interactive documentation is
disabled by default to reduce public surface area. All study endpoints require the signed session
cookie; state-changing browser and JSON requests also require same-origin CSRF validation.

## JSON endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/jobs/{job_id}` | Poll tenant-scoped analysis state and progress. |
| `GET` | `/api/v1/search?q=...` | Search the authenticated tenant's analyses and notes. |
| `POST` | `/api/v1/documents/{document_id}/progress` | Record page and bounded reading time. |
| `GET` | `/health/live` | Process liveness; no authentication. |
| `GET` | `/health/ready` | Database and provider-configuration readiness. |

The server-rendered forms cover registration, login, courses, chapters, document uploads, job
start/retry/cancel, and notes. They use the same service layer and tenant-scoped repositories.

## Progress example

After loading a page and obtaining the `mfe_csrf` cookie:

```http
POST /api/v1/documents/00000000-0000-0000-0000-000000000001/progress
Origin: https://study.example.com
X-CSRF-Token: value-from-mfe_csrf-cookie
Content-Type: application/json

{"page_number":2,"seconds_delta":30}
```

## Provider API version

`AnalysisProvider` is the internal server-side extension point. Implementations accept a bounded
PDF batch and must return `BatchAnalysisOutput`; the worker independently validates page numbers
and the versioned schema before persistence. Built-ins are `fake`, `disabled`, and `openai`.

The current schema and prompt identifiers are stored with every page result. A provider change
must add contract tests, typed failure mapping, and documentation. It must never expose keys or
raw object-store paths to a client, silently fall back to a paid provider, or bypass job limits.
