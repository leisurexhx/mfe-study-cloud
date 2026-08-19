# v1.0 release-candidate checklist

This matrix must be updated with fresh evidence immediately before tagging or publishing.

| # | Gate | Evidence |
| --- | --- | --- |
| 1 | Independent repository; private source unchanged | Separate `.git`; source read-only status audit |
| 2 | No private data, paths, keys, screenshots, or history | `privacy_scan.py --history`; manual history review |
| 3 | Clean README start and full stack | `docker compose config`; CI container smoke job; manual fresh-host walkthrough |
| 4 | Fake-provider no-cost end to end | Web/worker integration test and anonymous fixture walkthrough |
| 5 | Real provider server-side and bounded | Provider contract tests; config, limiter, token-budget tests |
| 6 | PostgreSQL migrations and downgrade path | Alembic upgrade/check/downgrade tests |
| 7 | S3-compatible tenant-safe storage | Object-key, encryption setting, and tenant HTTP tests |
| 8 | Recoverable queued jobs | Retry, partial, cancel, lease reclaim, idempotency tests |
| 9 | Multi-user/tenant isolation | Two-tenant service and HTTP tests |
| 10 | Complete responsive/PWA journey | Browser desktop/mobile smoke; PWA cache-policy test |
| 11 | Security/privacy baseline | Threat model, CSRF/session/CSP tests, privacy and Bandit scans |
| 12 | Operations documentation | Deployment, backup, restore, upgrade, logging, health docs |
| 13 | Open-source governance | License, contributing, conduct, security, issue/PR templates |
| 14 | CI and packaging | Python 3.11/3.12 jobs, audit, build, Twine check, clean-wheel import |
| 15 | Publication requires explicit approval | No remote/push/deploy; publication runbook only |

Gate 3 remains a release blocker until the Compose smoke job or a fresh Docker host completes
successfully. Do not create a release tag solely from static YAML validation.
