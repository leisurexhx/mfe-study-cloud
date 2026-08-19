# Project instructions

- This repository is the public, cloud-hosted edition of MFE Study Cloud.
- The private sibling project is read-only reference material. Never edit,
  move, or copy its private data, Git history, machine paths, hostnames, or deployment files.
- Model API calls are allowed only behind `AnalysisProvider` implementations running on the
  server or worker. Browser code must never receive provider credentials.
- Tests and CI must use `FakeAnalysisProvider` or `DisabledProvider` and must never make a paid
  model request.
- Every business record must be tenant scoped. Repository and service methods must require an
  explicit tenant identifier, and object keys must be derived from server-owned identifiers.
- Database changes require an Alembic migration and tests. PostgreSQL is authoritative; SQLite
  may be used only for narrow unit tests that do not claim PostgreSQL-specific behavior.
- All state-changing browser requests require authentication and CSRF validation. Uploads must
  be bounded, validated as real PDFs, and stored through the object-store abstraction.
- Never accept arbitrary SQL, filesystem paths, object-store keys, callback URLs, or provider
  endpoints from untrusted clients.
- Keep secrets out of source, templates, JavaScript, logs, test snapshots, and Git history.
- Preserve UTF-8, accessible touch targets, and responsive behavior for iPad and phones.
- Keep dependencies and external assets documented and license-compatible with AGPL-3.0.
- Do not push a remote, deploy publicly, or enable real provider calls without explicit user
  confirmation.
