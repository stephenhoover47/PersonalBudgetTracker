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

The feature branch is `feature/household-mvp`; [PR #2](https://github.com/stephenhoover47/PersonalBudgetTracker/pull/2) contains the implementation. Functional commit `0b976d3c2a9bdc5715fc42bde531069e77c530d4` passed hosted SQLite/PostgreSQL tests, desktop/mobile browser workflows and the production Docker build/runtime checks.

### Live Sandbox — November 7, 2026

- URL: https://hearth-mvp-staging-sandbox.up.railway.app
- Railway project: Personal Budget Tracker 0.0.1; environment: **Sandbox**; service: **Hearth MVP Staging**.
- Deployment: `b4f8f8c2-0001-4d3a-a2fe-647b5320d1f1`, observed **SUCCESS**.
- Source is pinned to the passing functional commit. Future branch pushes do not auto-deploy.
- Neon: a separate Free-plan project, `PersonalBudgetTracker MVP staging`, with database `hearth_mvp_staging`, PostgreSQL 17 and fixed 0.25 CU compute. Existing financial databases were not queried or modified.
- Both services remain on existing Free plans; no paid subscription was enabled. Free-tier quotas and cold starts may affect availability. Production services are unchanged.

APP_ORIGIN is the explicit HTTPS URL above. The generated domain routes to **8080**, matching Railway's actual PORT. Do not infer that runtime port from Docker EXPOSE. Create the domain and set the correct origin before relying on startup: an unresolved domain reference intentionally fails the production-origin check.

The pre-deploy command is `python -m household.staging_prepare`. It validates the staging database/hostname/environment allowlist before applying the code-managed Alembic migration and provisioning two sample accounts. It accepts SQLAlchemy URL objects without masking the password. The image smoke test executes this full command against disposable PostgreSQL, rather than testing only the migration and seed separately.

Sample logins are `stephen@example.test` and `claire@example.test`. Distinct random credentials are held in Railway variables and supplied privately to the owner; never put them in source, logs, PRs or screenshots. The seed refuses non-staging targets and never resets existing users/passwords or adds sample data over an existing household. Production provisioning remains the separate administrative CLI.

The Sandbox is for sample-data review. Before a production release, complete real-device Safari checks, review recovery/MFA requirements, approve the production configuration and costs, verify backups, and establish any real-data import mapping. Production release and real financial-data migration are separate approvals.


### Usability follow-up

Category rows open the selected month’s transactions, clearing stale filters. Sorting is performed before pagination: newest/oldest date or highest/lowest signed transaction amount, with optional refunds/reimbursements first. Split transactions show their full amount; category allocations remain visible in the editor.

Category budgets now repeat from the latest explicitly saved plan at or before the selected month. An explicit zero disables a recurring amount; turning rollover off resets carried balances. Overrides apply forward until a later explicit plan replaces them. Rollover walks intervening months even if nobody visited them, carrying both positive and negative balances. Historical changes recalculate subsequent inherited plans. Dashboard reads never create budget rows. The legacy copy endpoint remains for explicit snapshots; routine use requires no copying.

Savings allocations have visible amount/name editing and deletion (with confirmation). They are recurring monthly targets, separate from spending and actual bank balances. Deletion is scoped to the signed-in household and selected month. This release adds no migrations and does not reset existing sandbox data.

For travel, record purchases on their posted date and fund a dedicated rollover category before booking. Savings earmarks are planning aids, not proof that cash is funded. Planned travel versus routine spending, trip tagging, and goal balances are future enhancements; do not redate or hide real purchases to smooth a monthly chart.


### Recurring savings and plain-language follow-up

Savings targets now inherit the latest saved amount by goal name, as budgets do. Each month may override a target. Editing or renaming an inherited target writes only to the selected month; historical rows stay unchanged. A zero override stops a plan from that month onward until a later explicit override restarts it. Delete uses that zero marker so older plans cannot unexpectedly reappear. Renaming stops the old name and starts the new one in the selected month. Existing earlier zero allocations are treated as stop markers. Savings names currently identify recurring series; a later change to goal IDs should be a deliberate migration when funded-bucket tracking is introduced. Dashboard GETs do not materialize any rows.

The mobile overview uses single-column cards with descriptions: Spent this month, Spending limit this month, Monthly savings target. A persistent, dismissible confirmation is visible after successful saves without scrolling back to the header. The savings target explicitly does not represent money actually transferred or an available balance.

Shared savings accounts can be added/imported through CSV. Owned-account transfers are excluded from spending on either side, even when only one side is imported. The MVP does not automatically pair transfer legs, synchronize bank bucket balances, or calculate funded goal balances. Future funded-goal tracking should reconcile an opening balance plus actual allocations/withdrawals, show monthly target versus actual contribution versus available balance, and avoid treating two imported transfer legs as two contributions. Bank accounts remain the authority for money movement; virtual app buckets would be planning/reconciliation records only. No live aggregator or real account import is enabled by this change.
