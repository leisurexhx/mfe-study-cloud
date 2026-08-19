# Changelog

All notable changes are documented here. This project follows Semantic Versioning.

## [Unreleased]

- No changes yet.

## [1.0.0-rc.2] - 2026-08-19

### Changed

- Raised the build and CI `setuptools` baseline to 83 after the GitHub Python 3.11 runner's
  bundled version was reported under `PYSEC-2026-3447`.
- Clarified that OpenAI-compatible Chat Completions endpoints cannot replace the current
  Responses API PDF provider without a dedicated extraction and provider implementation.

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
- Reusable full-stack Compose smoke journey covering Fake Provider analysis and tenant isolation.

### Fixed

- Prevented the non-HTTP Worker process from inheriting the Web process health check.
- Embedded the pinned MinIO release and commit metadata in the source-built binary.
