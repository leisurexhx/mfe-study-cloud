# MFE Study Cloud

MFE Study Cloud is an open-source, cloud-hosted study reader for turning course PDFs into
page-aligned bilingual explanations, formulas, terms, notes, and searchable learning history.
It is designed as an installable PWA and a self-hosted server product.

> Status: `v1.0.0-rc.1` release-candidate source is prepared; a real Docker Compose smoke test
> is still required before tagging. The safe demo provider is the default, and real model calls
> are never made unless a server administrator explicitly enables them.

## Product boundary

- Multi-user and tenant-scoped from the database through object storage.
- PostgreSQL is the system of record; S3-compatible storage holds PDFs and rendered assets.
- A database-leased worker performs bounded PDF analysis jobs.
- The browser never receives an OpenAI API key or any other provider secret.
- `FakeAnalysisProvider` powers tests and the no-cost end-to-end demo.
- The OpenAI provider uses the Responses API with PDF file input and versioned structured output.

The private local-first application that inspired this project is not part of this repository.
No private course files, user notes, deployment hostnames, or Git history are included.

## One-command development start

```bash
cp .env.example .env
docker compose up --build
```

When the containers are healthy, open `http://localhost:8080`. Register, create a course and
chapter, upload `tests/fixtures/anonymous-demo.pdf`, and start analysis. The default fake provider
completes the entire queue/reader/search/progress flow without a key, model network request, or
cost. The first start compiles the pinned MinIO community source image and can take several
minutes. See [development](docs/development.md).

Docker Engine 25+ and Docker Compose 2.24+ are recommended. `docker compose down` preserves data;
adding `--volumes` intentionally deletes development data.

Install the PWA from the browser's install action, or use **Add to Home Screen** on iPhone/iPad.
Private documents remain online-only by design; see the [development walkthrough](docs/development.md).

## Real provider safety

Real API use is opt-in and server-side only. Administrators will set:

```dotenv
MFE_ANALYSIS_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=...
MFE_ANALYSIS_REQUESTS_PER_MINUTE=30
MFE_ANALYSIS_JOB_MAX_OUTPUT_TOKENS=200000
```

Never add these values to browser settings, source files, images, logs, issue reports, or Git.
The application remains bootable with the fake or disabled provider and no API key.

OpenAI processing sends bounded PDF batches to a third party. Review [privacy and retention
boundaries](docs/privacy.md) and [production deployment](docs/deployment.md) before enabling it.

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
python scripts/privacy_scan.py --history
```

## License

GNU Affero General Public License v3.0 only (`AGPL-3.0-only`). Dependency and asset license
compatibility must be rechecked before every public release. See the recorded [dependency and
asset license review](docs/dependency-licenses.md).

## Documentation

- [Product specification](docs/product-spec.md) and [architecture](docs/architecture.md)
- [Development](docs/development.md), [deployment](docs/deployment.md), and
  [operations/recovery](docs/operations.md)
- [HTTP/provider API](docs/api.md), [privacy](docs/privacy.md), and
  [threat model](docs/threat-model.md)
- [PWA/native/SaaS product paths](docs/product-distribution.md)
- [Release gates](docs/release-checklist.md) and [GitHub publication runbook](docs/github-release.md)
