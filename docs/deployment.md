# Production deployment

The provided deployment is a single-host reference: Caddy terminates TLS, FastAPI serves the
web/PWA, PostgreSQL owns metadata, MinIO stores documents, and a separate worker performs
analysis. Larger installations can replace each stateful service with a managed equivalent.

## Required configuration

Create `.env` outside image layers and set at least:

```dotenv
MFE_ENV=production
MFE_DOMAIN=study.example.com
MFE_PUBLIC_BASE_URL=https://study.example.com
MFE_ALLOWED_HOSTS=study.example.com
MFE_SESSION_SECRET=replace-with-at-least-32-random-characters
MFE_SECURE_COOKIES=true
MFE_POSTGRES_PASSWORD=replace-with-a-long-random-password
MFE_OBJECT_ACCESS_KEY=replace-with-a-random-access-key
MFE_OBJECT_SECRET_KEY=replace-with-a-long-random-secret
MFE_OBJECT_SSE=AES256
# Generate a random 256-bit value; losing this key makes encrypted MinIO data unreadable.
MFE_MINIO_KMS_SECRET_KEY=mfe-sse:replace-with-base64-encoded-256-bit-key
MFE_ANALYSIS_PROVIDER=disabled
```

Keep `.env` readable only by the deployment account. A production secret manager is preferred.
The reference MinIO service requires the KMS key for SSE-S3; back it up separately under strict
access control. Managed S3 deployments should use their provider's equivalent encryption policy.
Do not pass secrets through browser configuration, image build arguments, source control, issue
reports, or logs.

Start and inspect:

```bash
docker compose -f compose.yml -f compose.production.yml config --quiet
docker compose -f compose.yml -f compose.production.yml up --build -d
docker compose -f compose.yml -f compose.production.yml ps
curl --fail https://study.example.com/health/ready
```

DNS must point `MFE_DOMAIN` to the host and ports 80/443 must be reachable. Caddy obtains and
renews certificates. Direct web and MinIO ports are removed by the production override.

## Enabling OpenAI deliberately

After reviewing [privacy](privacy.md), account limits, model availability, and expected spend:

```dotenv
MFE_ANALYSIS_PROVIDER=openai
OPENAI_API_KEY=replace-in-the-server-secret-store
OPENAI_MODEL=administrator-selected-model
MFE_ANALYSIS_REQUESTS_PER_MINUTE=30
MFE_ANALYSIS_MAX_OUTPUT_TOKENS=20000
MFE_ANALYSIS_JOB_MAX_OUTPUT_TOKENS=200000
```

Restart web and worker after changing settings. The key is read only by trusted server processes.
Quota exhaustion becomes a non-retryable job state; transient rate limits use bounded retries.
When multiple worker containers are deployed, divide the account request allowance between them,
because the rolling limiter is shared within one worker process, not across hosts.

## Hardening checklist

- Restrict database and object storage to the private network.
- Use encrypted volumes as well as S3 server-side encryption.
- Put database, object-store, and `.env` backups under separate access control.
- Monitor health endpoints, failed/partial jobs, disk usage, and certificate renewal.
- Pin and regularly update images and Python dependencies after tests.
- Test restore procedures and tenant-isolation tests before each release.
