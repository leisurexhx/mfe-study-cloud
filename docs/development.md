# Development and fake-provider walkthrough

## Container start

Requirements: Git, Docker Engine 25+ and Docker Compose 2.24+.

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080`. Register, create a course and chapter, upload
`tests/fixtures/anonymous-demo.pdf`, then select **Start analysis**. The default `fake`
provider is deterministic, makes no external model request, costs nothing, and is the only
provider used by CI.

To install the PWA, use the browser's **Install app** action on desktop/Android. On iPhone or iPad,
open the Share menu and choose **Add to Home Screen**. Production installation requires HTTPS;
`localhost` is accepted by supporting browsers for development. The installed app still requires
the server for private pages and analysis because private responses are deliberately not cached.

Stop the stack with `docker compose down`. Add `--volumes` only when you intentionally want to
delete the development database and object store.

The first MinIO image build compiles the pinned community source release and can take several
minutes. This avoids depending on an unmaintained precompiled community image.

## Native development

Run PostgreSQL and an S3-compatible service, copy `.env.example` to `.env`, and set their
connection values. Then:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
alembic upgrade head
mfe-study-cloud
```

In another terminal, activate the same environment and run `mfe-study-worker`. On Windows,
activation is `.venv\Scripts\Activate.ps1`.

## Required checks

```bash
python -m ruff check .
python -m mypy
python -m pytest
python scripts/privacy_scan.py --history
python -m bandit -q -r src -c pyproject.toml
python -m pip_audit --skip-editable
python -m build
python -m twine check dist/*
```

Do not add live-provider tests to the standard suite. Do not use real PDFs, real credentials,
personal notes, or production logs as fixtures.
