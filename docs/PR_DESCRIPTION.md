# Add a secure two-member household budgeting MVP with CSV ingestion

The existing API exposes unauthenticated Plaid and analytics routes, trusts user-supplied ownership IDs and returns bank access tokens. This change replaces the runtime with a household-scoped application and adds a working React/TypeScript interface. Personal accounts stay outside the household budget; no paid aggregator or live bank credentials are required.

## Implementation

- Two administratively provisioned users, individual Argon2id passwords, opaque hashed sessions, production Secure cookies, CSRF/origin checks, DB-backed login throttling and safe request/error logging.
- Independent hh_* schema and explicit Alembic revision/version table. Legacy tables and data remain untouched; legacy routers are not mounted. Migration autogeneration ignores unrelated tables.
- Integer USD cents; explicit purchases, payments, transfers, income, contributions, refunds, reimbursements, savings transfers and loan payments. Spending splits enforce totals/signs/category ownership. Transaction versions protect concurrent edits; bulk changes/import commits are atomic and household writes serialize.
- Standard, Chase and Capital One CSV adapters; preview, signed file-total reconciliation, stable-ID/occurrence-based deduplication, import history and explicit Needs review classification. Conflicting source IDs stop imports.
- Responsive dashboard, merchant/type/account/category filters, pagination, single/bulk classification, transaction splitting, editable fixed/flexible categories, explicit monthly budgets, contiguous positive/negative rollover, and monthly savings earmarks.
- Local provisioning/password-reset CLI, sample CSV, operating guide, nonroot same-origin Dockerfile and SQLite/PostgreSQL/browser CI workflows.

## Validation

31 backend tests, 2 frontend unit tests and 2 desktop/mobile browser workflows passed locally. Production frontend builds and TypeScript checks pass. Fresh/repeat migrations and no-drift checks pass on SQLite, including legacy-data preservation. PostgreSQL dialect migration SQL compiles offline. Ruff and npm/pip dependency checks are recorded in docs/VALIDATION.md.

Live PostgreSQL, Docker runtime, GitHub CI and real Safari/device testing remain staging gates. No production deployment, real-data mutation, bank connection or paid service was used.

## Setup and review

Follow the root README: create a Python virtualenv, install backend dependencies, run `alembic -c household-alembic.ini upgrade head`, provision two users using `python -m household.cli init-household`, then run the API and React frontend. Use only a fresh local/staging DB for initial testing. Production requires HTTPS APP_ORIGIN, an explicit PostgreSQL DATABASE_URL, backups and explicit deployment approval.

## Remaining risks / limits

Private two-user MVP; no MFA/email recovery (admin CLI reset revokes sessions), automatic bank sync, pending transactions, foreign currencies, balance reconciliation ledger or legacy-data conversion. CSVs without stable IDs can be ambiguous under partial-day exports or changed source descriptions. Imported amounts are immutable through the UI; classification/splits are editable. Savings plans do not move money or reduce the spending budget remainder. See OPERATIONS.md for retention/edge limiting and a future aggregator adapter contract.

## Review and staging status

Published on `feature/household-mvp`; [PR #2](https://github.com/stephenhoover47/PersonalBudgetTracker/pull/2) is open. Initial hosted SQLite/PostgreSQL migration/API checks and desktop/mobile browser workflows passed. The staging-preparation commit adds a Docker build/runtime check and isolated sample-user bootstrap tests.

A fresh Neon Free-plan staging database and a staged-only Railway Sandbox service are prepared. No Railway compute has started; applying that configuration requires hosting-cost approval. Existing production services and financial data are untouched.
