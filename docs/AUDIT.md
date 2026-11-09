# Repository audit — 2026-11-07

Audited upstream master `92a48e78eae13ac1a89495285525ae6ff525fa81`, including API, ORM, SQL analytics, Plaid sync/client, dependencies, migration environment and deployment files.

## Critical findings
- All analytics and Plaid routes are unauthenticated. Caller-supplied user IDs permit impersonation; sync finds items by access token without enforcing ownership. Exchange returns bank access tokens; storage is plaintext.
- Wildcard credentialed CORS, raw exception disclosure, and no CSRF/session/rate-limit implementation.
- SQL analytics count positive amounts without excluding transfers/payments and omit uncategorized transactions. Money uses Float. Income/refund signs are inconsistent. Some interval placeholders are embedded inside SQL literals.
- Sync does not implement safe pagination/retry, blindly inserts additions, skips unknown accounts, and advances cursors despite skipped records. Two overlapping Plaid implementations exist.
- Startup runs create_all and suppresses failures. Alembic has an environment but no revisions. No automated tests or frontend exist on master.
- Dependencies are a 2025 environment freeze with unused packages; production config lacks an explicit migration/release process.

## Decision
Keep FastAPI, SQLAlchemy, PostgreSQL/Neon compatibility and the repository history. Replace the runtime entrypoint; legacy code remains historical reference only and is not mounted or imported. Build independently named `hh_*` tables with explicit migrations, preserving legacy tables. Do not automatically migrate legacy data: ownership, sign conventions and credentials need a reviewed mapping.

Use same-origin React/TypeScript + FastAPI, opaque hashed server-side sessions, Argon2id passwords, CSRF tokens and origin checks, explicit household scope on every resource. Provision exactly two users via an administrative CLI with hidden password input; no public registration or household joining. USD integer cents, signed outflows (negative inflows), explicit transaction kinds and split allocations. CSV adapters normalize into one ingestion contract; no live aggregator in the MVP.

## Scope and assumptions
Only joint/shared-account activity belongs here; personal accounts are deliberately excluded. Both members have equal household permissions. Posted transactions only, USD only. Planned savings are earmarks, never bank transfers. No guessed payment classification: imports default to `review` and are excluded until classified. Monthly budget rows are explicit snapshots; copying a month is an intentional action. Positive and negative rollover carry forward only through contiguous configured months. Loan payments count as cash budget spending (principal + interest); investments/savings transfers do not. Refunds/reimbursements reduce category spending in the month received. Income and contributions are separate inflows, never negative expenses.
