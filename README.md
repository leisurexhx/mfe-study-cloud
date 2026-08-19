# MFE Study Cloud

MFE Study Cloud is an open-source, cloud-hosted study reader for turning course PDFs into
page-aligned bilingual explanations, formulas, terms, notes, and searchable learning history.
It is designed as an installable PWA and a self-hosted server product.

> Status: `v1.0.0-rc.1` is under active construction. The safe demo provider is the default;
> real model calls are never made unless a server administrator explicitly enables them.

## Product boundary

- Multi-user and tenant-scoped from the database through object storage.
- PostgreSQL is the system of record; S3-compatible storage holds PDFs and rendered assets.
- A database-leased worker performs bounded PDF analysis jobs.
- The browser never receives an OpenAI API key or any other provider secret.
- `FakeAnalysisProvider` powers tests and the no-cost end-to-end demo.
- The OpenAI provider uses the Responses API with PDF file input and versioned structured output.

The private local-first application that inspired this project is not part of this repository.
No private course files, user notes, deployment hostnames, or Git history are included.

## Planned one-command development start

```bash
cp .env.example .env
docker compose up --build
```

When the containers are healthy, open `http://localhost:8080`. Full setup and the fake-provider
walkthrough will be documented in `docs/development.md` before the release candidate is tagged.

## Real provider safety

Real API use is opt-in and server-side only. Administrators will set:

```dotenv
MFE_ANALYSIS_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

Never add these values to browser settings, source files, images, logs, issue reports, or Git.
The application remains bootable with the provider disabled or without a key.

## Repository map

- `src/mfe_study_cloud/` — application, domain services, providers, worker, and web UI
- `migrations/` — explicit PostgreSQL schema migrations
- `tests/` — provider-free unit, integration, tenant-isolation, and security tests
- `docs/` — product, architecture, operations, API, and release documentation
- `deploy/` — container and reverse-proxy examples without private infrastructure values

## Development checks

```bash
python -m pytest
python -m ruff check .
python -m mypy
```

## License

GNU Affero General Public License v3.0 only (`AGPL-3.0-only`). Dependency and asset license
compatibility must be rechecked before every public release.

