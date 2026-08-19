# ADR 0002: PostgreSQL, S3-compatible storage, and database-leased jobs

- Status: accepted

## Decision

Use PostgreSQL as the system of record, S3-compatible object storage for PDFs/assets, and a worker
that claims PostgreSQL job rows with bounded leases. MinIO supplies the development object service.

## Why

SQLite and local paths cannot safely serve multiple Internet users across multiple processes.
PostgreSQL supports tenant constraints, transactional page persistence, full-text search, and
`FOR UPDATE SKIP LOCKED`. Database-leased jobs avoid a Redis dependency while retaining reclaimable
work, heartbeats, retries, and cancellation.

## Consequences

PostgreSQL behavior needs container integration tests. Very high throughput could later justify a
dedicated queue without changing the domain job state machine.

