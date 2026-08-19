# Dependency and asset license review

This is a release review record, not legal advice. The project is `AGPL-3.0-only`. Direct Python
dependencies are permissive or weak-copyleft packages commonly usable with an AGPL application:

| Dependency | Recorded license family |
| --- | --- |
| Alembic, FastAPI, Jinja2, jsonschema, Pydantic, pydantic-settings, SQLAlchemy | MIT or BSD |
| boto3, OpenAI Python SDK, python-multipart | Apache-2.0 |
| Argon2-cffi, itsdangerous, pypdf, Uvicorn | MIT or BSD |
| Pillow | MIT-CMU |
| psycopg 3 | LGPL-3.0-only |
| pypdfium2 / PDFium artifacts | Apache/BSD-style package and upstream component notices |

Runtime services remain separate processes: PostgreSQL uses the PostgreSQL License, Caddy uses
Apache-2.0, and MinIO Community is AGPLv3. The MinIO container builds a pinned public source tag so
corresponding source remains identifiable. Generated icons and the anonymous PDF fixture were
created for this project and are distributed under the repository license; there are no external
fonts, CDN assets, copied course materials, or private screenshots.

Before a public tag, run `pip-licenses`, inspect transitive notices and container SBOMs, confirm
the recorded versions have not changed their terms, and preserve all required notices. Resolve any
unknown or proprietary license before distribution.
