# Database migrations

Run `alembic upgrade head` before starting the web or worker process. The database URL comes from
`MFE_DATABASE_URL`; tests may override it through Alembic's programmatic configuration.

Downgrades are intended for development only. Back up PostgreSQL and object storage together before
running schema changes in production.
