# Operations and security

## Before any production release

1. Obtain explicit approval to deploy. Review the diff, automated results and risks. No production deployment has been performed by this change.
2. Use a new PostgreSQL database/branch for staging. Set `DATABASE_URL=postgresql://...?...sslmode=require`, `APP_ENV=production`, `APP_ORIGIN=https://your-host`. HTTPS and same-origin hosting are required; wildcard CORS is absent. Do not put database passwords in Git, logs, browser bundles or issue bodies.
3. Back up and test a restore before applying migrations to any existing database. Run `alembic -c household-alembic.ini upgrade head` from backend. This creates only new hh tables, uses a separate version table, and never modifies legacy tables. Startup does not mutate schema. Downgrade is intentionally blocked; restore backups or write a reviewed forward migration.
4. Run `python -m household.cli init-household` in a trusted admin session. It refuses to initialize over an existing household and creates exactly two users atomically. No public signup/invite endpoint exists. Do not reuse sample passwords.
5. Build root Dockerfile and run with the environment above. Configure a proxy limit of 2.5 MB, TLS, request timeouts and coarse IP rate limiting. Only trust forwarded headers from your proxy. Health check `/health` verifies DB connectivity and household table presence. Keep `/docs` off in production (automatic).
6. Verify sign-in as both members, secure cookie attributes, CSV preview/commit on sample data, category editing, splits, refunds, payments and restored backups in staging.
7. Configure backups/retention, uptime/error alerts and ownership. Database access should be limited to this service and administrators. Do not grant access to production financial data for automated testing.

## Sessions and passwords

Passwords use Argon2id. Session cookies are HttpOnly, SameSite Strict, Secure in production and expire after seven days. The DB stores only SHA-256 session-token hashes. Login rotates the current browser session; logout revokes it. Administrative `python -m household.cli reset-password` resets the password via hidden prompts and revokes all the member’s sessions. No email password recovery/MFA exists yet. CSRF validation requires both the session-specific header token and a custom request header; supplied Origin must match APP_ORIGIN. The frontend does not store tokens in localStorage.

Login attempts are limited by normalized email and direct network peer (20 attempts/15 minutes, including successful logins), using shared DB state. Behind a reverse proxy the peer limit may apply across both members. A distributed edge limit is still recommended before wider exposure. Provisioning is admin-only, so the supported product is a private two-person household.

## Data and observability

HTTP logs contain request ID, method, status and duration; not cookies, paths with financial queries, bodies, credentials or raw DB exception strings. Mutation audit rows record actor, action and resource ID. They are operational records, not immutable compliance logs or before/after financial snapshots. Errors have safe messages; database uniqueness conflicts return 409. Transaction edits have optimistic version checks; budget/category/plan edits are serialized, last-write-wins. All household writes serialize on the household row; this is appropriate for two users.

Import previews retain normalized financial rows. Uncommitted previews expire after 24 hours but remain in the database; establish a retention policy and an admin purge procedure before broader use. Session and throttle cleanup occurs on login. No telemetry or external financial APIs are called.

## Deliberate MVP limits

- USD, posted transactions, one household and two provisioned users. No balance/net-worth ledger, FX, transaction deletion/undo, pending-to-posted matching, automatic transfer matching or bank synchronization. Misclassified rows can be corrected; erroneous source amounts require an administrator-reviewed correction rather than silently mutating imports.
- CSV totals reconcile a file, not account balances. ID-less partial exports can confuse identical purchases. Stable external IDs are best. Bank export layouts may change; adapters fail on missing columns, but users must confirm date/sign conventions.
- Income, contributions, expenses, refunds and planned savings are reported independently; this app does not imply that a card budget remainder is a bank cash balance.
- No automated legacy-data migration. Legacy float amounts, ownership and exposed token history require separate review; rotate any credentials previously exposed by the old API before reusing bank integrations.
- Password reset requires administrator access. No MFA, passkeys, email delivery, export UI or offline mode. Personal spending is kept outside the app, not hidden from a partner within a shared account.
- Aggregator implementation is deferred. A future adapter must emit the normalized ingestion contract, add namespaced provider IDs, encrypted credential storage, household-scoped server-side token lookup, safe cursor pagination, retries and pending/posted reconciliation. Do not reactivate the legacy endpoints.

## Repository and staging status

The feature branch is published as `feature/household-mvp` and PR #2 is open:
https://github.com/stephenhoover47/PersonalBudgetTracker/pull/2

The initial hosted checks passed against SQLite and PostgreSQL 16, including migrations and desktop/mobile browser workflows. The follow-up staging-preparation commit adds a Docker build/runtime smoke check and one-time sample-user provisioning tests.

An isolated Neon Free-plan project, `PersonalBudgetTracker MVP staging`, was created in US East with PostgreSQL 17 and fixed 0.25 CU compute. Its dedicated database is `hearth_mvp_staging`; existing Neon projects/databases were not read or modified. Connection credentials are staged as Railway variables and are never committed here.

A new `Hearth MVP Staging` service is prepared in the existing Railway project's **Sandbox** environment. Creation, feature-branch source, root Dockerfile, health check, explicit migrations, production cookie settings and database variables are staged only. No Railway deployment has been started. The source is pinned to a reviewed feature-branch commit so unrelated pushes cannot deploy automatically.

The staging pre-deploy command runs migrations, then `python -m household.staging_seed`. The seed refuses any target except APP_TIER=staging, the explicitly allowlisted database hostname, database `hearth_mvp_staging`, and a staging/Sandbox deployment environment. It creates two sample logins (`stephen@example.test` and `claire@example.test`) only when no household exists. Two distinct generated passwords are supplied through protected environment variables, never source or logs. Subsequent deployments leave existing users/passwords and household data unchanged. This helper must never be used for production provisioning.

Before committing the staged Railway changes: verify only this new service is affected, confirm the hosting cost authorization, use the latest passing commit, and generate a Railway HTTPS domain. APP_ORIGIN references the generated public domain. Apply service resource limits after the staged service exists (the Railway API cannot apply limits to a service that exists only in a staged patch). Verify terminal deployment success, HTTPS/login behavior and sample CSV reconciliation before sharing it for testing. Production release and real-data migration remain separate approvals.
