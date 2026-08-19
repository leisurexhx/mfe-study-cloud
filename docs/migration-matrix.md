# Migration matrix

| Source capability | Decision | Cloud implementation |
|---|---|---|
| Page-aligned PDF registration | Reuse behavior | Reimplement with tenant IDs and object storage |
| SHA-256 idempotency | Reuse | Tenant/document unique constraints and object metadata |
| JSON Schema import validation | Reuse and strengthen | Versioned Pydantic model plus JSON Schema validation |
| AI original vs revisions | Reuse | Immutable page analysis versions with active pointer |
| Formula/LaTeX safety | Reuse | Port generic normalization and validation tests |
| PDF rendering | Reuse behavior | Render from owned object bytes into controlled cache objects |
| Notes and reading progress | Reuse behavior | Tenant/user-scoped PostgreSQL tables |
| Search scopes and CJK fallback | Reuse behavior | PostgreSQL FTS plus bounded `ILIKE` fallback |
| CSRF, CSP, safe escaping | Reuse principles | Authenticated FastAPI middleware and templates |
| Local filesystem paths | Rewrite | S3 object keys generated only by server |
| SQLite/FTS5 repositories | Rewrite | SQLAlchemy/PostgreSQL repositories and migrations |
| Manual JSON import as primary flow | Replace | Background provider jobs; manual import may remain admin-only later |
| Local backup scripts | Rewrite | PostgreSQL dump plus object-store versioning/backup documentation |
| CLI and read-only MCP | Defer | Not required for v1 product journey |
| Course attachments beyond PDF | Defer | PDF-first v1; safe generic resources can follow |
| Private deployment host configuration | Drop | Generic localhost and reverse-proxy examples only |

