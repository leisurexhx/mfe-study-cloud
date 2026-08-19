# Privacy and data lifecycle

## Data held by this application

Accounts, memberships, courses, chapters, notes, reading progress, job metadata, and validated
analysis output are stored in PostgreSQL. Original PDFs and rendered page images are stored in the
configured S3-compatible object store. The application retains them until an administrator
removes them under the operator's published retention policy.

The v1 release candidate has no self-service account or document deletion route. Operators must
state this limitation before collecting user data and handle verified deletion requests through
an audited administrative procedure that removes database records, original objects, rendered
objects, and relevant backups according to local law. Backups can have a separate disclosed
expiry period.

Signed sessions last up to seven days. Application logs contain allowlisted operational metadata
only and should have an operator-defined short retention period. The service worker caches only
public static assets; authenticated HTML, APIs, PDFs, rendered pages, and analyses are not cached.

## Optional OpenAI processing

No document leaves the installation while `MFE_ANALYSIS_PROVIDER` is `fake` or `disabled`. If an
administrator enables `openai`, a worker sends each bounded PDF page batch, the document display
title, and analysis instructions to the Responses API. The implementation uses inline PDF input,
does not create persistent `/v1/files` objects, sets `store=False`, and does not use background
mode. It stores validated output, usage, latency, and response identifier locally.

`store=False` is not a promise of zero provider retention. OpenAI's current data-control
documentation says API data is not used to train models by default, abuse-monitoring logs can be
retained for up to 30 days by default, and approved organizations can configure Modified Abuse
Monitoring or Zero Data Retention subject to endpoint and file-input limitations. File inputs are
also scanned on submission and may be retained for manual review in the exceptional case described
by that policy. Operators must review the current official policy, contract, region, and user
consent before enabling the provider:

- <https://developers.openai.com/api/docs/guides/your-data>
- <https://openai.com/enterprise-privacy/>

Do not upload regulated, confidential, copyrighted, or personal course material unless the
operator has a lawful basis, appropriate provider terms, a suitable retention configuration, and
authorization from the rights holder. Users should be told which provider/model is active before
analysis.
