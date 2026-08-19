# Changelog

All notable changes are documented here. This project follows Semantic Versioning.

## [Unreleased]

- No changes yet.

## [1.0.0-rc.1] - 2026-08-19

### Added

- Independent AGPL repository with product, architecture, migration, privacy, threat-model,
  deployment, operations, and publication documentation.
- Tenant-scoped users, courses, chapters, documents, notes, search, and reading progress on
  PostgreSQL with Alembic migrations.
- S3-compatible document/render storage with server-generated keys and production encryption
  validation.
- Database-leased workers with batching, heartbeat, reclaim, cancellation, partial resume,
  idempotent page writes, bounded retry, request pacing, usage accounting, and token budgets.
- Fake, disabled, and OpenAI Responses API providers with versioned structured PDF analysis.
- Responsive server-rendered PWA, page-aligned reader, formula display, dashboard progress, secure
  sessions/CSRF/CSP, and privacy-safe service-worker caching.
- Docker Compose development/production stacks, JSON logs, health checks, GitHub CI, dependency
  audit, privacy scan, governance templates, and anonymous fixtures.
