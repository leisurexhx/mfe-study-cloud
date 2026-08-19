# Operations, backup, and recovery

## Health and logs

- `/health/live` proves the web process is responding.
- `/health/ready` verifies a database query and reports provider readiness without exposing keys.
- Web and worker logs are JSON with allowlisted identifiers. They intentionally omit document
  text, notes, cookies, credentials, provider payloads, and tracebacks.
- Raw HTTP access logging is disabled so search queries and user-controlled URLs do not enter
  application logs; collect only redacted aggregate traffic metrics at the trusted proxy.

Alert on repeated `analysis_internal_failure`, lease loss, readiness failures, partial/failed
jobs, storage capacity, database capacity, and unusual request volume.

## Consistent backup

PostgreSQL and object storage form one logical dataset. Pause new uploads and analysis workers,
wait for running jobs to finish or cancel them, and record the application version before taking
both snapshots.

```bash
mkdir -p backups
docker compose exec -T postgres pg_dump -U mfe -Fc mfe > backups/database.dump
docker run --rm -v mfe-study-cloud_object_data:/data:ro -v "$PWD/backups:/backup" \
  alpine:3.22 tar -czf /backup/objects.tar.gz -C /data .
```

Backups contain user documents and must be encrypted, access-controlled, retained for a defined
period, and restore-tested. Volume names can differ when Compose uses a custom project name; check
`docker volume ls` rather than guessing.

## Restore drill

Restore into an isolated environment first. Verify the backup version and hashes, restore the
object snapshot, recreate an empty database, then run:

```bash
pg_restore --clean --if-exists --no-owner --dbname=mfe database.dump
alembic upgrade head
```

Start with `MFE_ANALYSIS_PROVIDER=disabled`, check `/health/ready`, log in with a test account,
open stored pages, and confirm tenant isolation before enabling workers. A restore using `--clean`
overwrites existing database objects; never run it against a production target without an
approved maintenance window and a verified rollback copy.

## Upgrade and rollback

1. Back up both data stores and record the current image/version.
2. Review `CHANGELOG.md` and migration scripts.
3. Build and test the new image with the fake provider.
4. Run the migration job once, then start web and worker.
5. Roll application containers back if needed. Database rollback requires an explicitly reviewed
   downgrade or restore; do not assume every schema migration is lossless.
