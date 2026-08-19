# Threat model

## Assets and trust boundaries

Protected assets are credentials, signed sessions, tenant metadata, PDFs, rendered pages, notes,
analysis output, usage/cost records, and backups. The browser is untrusted. Web and worker are
trusted application processes; PostgreSQL and object storage are private infrastructure. A real
analysis provider is a separate processor with its own policy boundary.

| Threat | Primary controls | Verification |
| --- | --- | --- |
| Cross-tenant access or identifier guessing | Tenant ID on business rows, tenant-scoped repositories, ownership check before object reads | Adversarial two-tenant service and HTTP tests |
| Credential/session theft | Server-only secrets, Argon2id, signed HttpOnly cookies, TLS/secure-cookie production validation | Config and header tests; privacy scan |
| CSRF and hostile embedding | Strict Origin plus session/cookie token, SameSite cookies, frame denial | Web security tests |
| XSS or external asset injection | Jinja autoescape, restrictive CSP, bundled assets | Security-header and template tests |
| Malicious or oversized PDF | Byte/page bounds, signature/parser validation, isolated batch processing | Upload and PDF-batch tests |
| Object-key traversal | Server-generated tenant/document keys; clients never submit keys | Object-store and tenant tests |
| Duplicate processing or worker crash | Idempotency key, row lock, lease, heartbeat, reclaim, page versions | Queue concurrency/recovery tests |
| Unexpected spend | Fake default, explicit provider opt-in, concurrency/request/token/page/byte limits, bounded retry | Provider, limiter, budget, and job tests |
| Sensitive logs or repository history | Allowlisted JSON fields, no raw traceback/content, current/history privacy scanner | Logging and scanner checks |
| Stale/offline private response | Service worker caches public static assets only | PWA cache-policy test |

## Residual risks

- Application-level tenant filters are not database row-level security. A new repository query can
  violate the invariant unless it follows the required pattern and receives isolation tests.
- PDF parsing and image rendering process untrusted complex files; production deployments should
  apply container resource limits and timely library updates.
- The rolling request limiter coordinates one worker process, not a distributed fleet.
- A compromised host or deployment secret can access all tenants; secret management, host
  hardening, encrypted backups, and least privilege remain operator responsibilities.
- Self-service deletion, MFA, audit-log export, moderation policy, and enterprise identity are not
  implemented in this release candidate.

Report suspected vulnerabilities through `SECURITY.md`, never a public issue containing private
data or an active credential.
