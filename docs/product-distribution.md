# Product and distribution paths

## Recommended first product

Ship the responsive PWA first. One codebase covers desktop and mobile browsers, installation uses
the web manifest, and updates remain server-controlled. The release candidate intentionally caches
only the public shell assets, so private learning data does not remain in an offline cache.

## Open-source distribution

Publish the independent AGPL repository with source, fixture, Compose stack, migrations,
operations guidance, threat model, contribution templates, and repeatable CI. The default demo
must remain free of provider calls. Provide checksums and release notes for tags, but do not publish
deployment secrets or a pre-populated data volume.

## Later native packaging

If stores or device integration justify the maintenance cost, wrap the hosted PWA with a small
native shell after stable production use. Before store submission, add account deletion, privacy
disclosures, support/contact channels, content rights workflow, accessibility review, telemetry
consent if telemetry is introduced, store artwork, signing, and platform-specific purchase rules.

Payments and SaaS operations are separate product work: billing ledger, plans/quotas, tax,
refunds, abuse response, email verification, rate limits across replicas, admin support tooling,
data-export/deletion, DPA/privacy terms, monitoring, and incident response. None is implied by this
self-hosted release candidate.
