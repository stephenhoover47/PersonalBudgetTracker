# Validation — November 7, 2026 (America/New_York)

## Executed locally

| Check | Result |
| --- | --- |
| Backend API, ingestion and operations tests | **31 passed**, Python 3.12, pytest 9.0.3 |
| Frontend unit tests | **2 passed**, Vitest 5.1.0 |
| Desktop browser household workflow, 1440 × 1000 | **Passed** |
| iPhone-sized browser household workflow, 390 × 844 | **Passed** |
| TypeScript compilation and production Vite build | **Passed** |
| Fresh SQLite migration, repeat upgrade, schema drift check | **Passed** |
| Legacy sentinel table and data preserved through migration/check | **Passed** |
| PostgreSQL dialect offline migration SQL generation | **Passed** (not a live PostgreSQL execution) |
| Ruff checks on active backend, migrations and tests | **Passed** |
| npm audit, including development dependencies | **0 known advisories** at check time |
| pip-audit production and development dependency resolutions | **0 known advisories** at check time |

The browser tests cover separate login, shared-account creation, CSV upload/preview/reconciliation/commit, merchant filtering, category splitting, budget updates, savings allocation, dashboard display and logout. Both widths were checked for page overflow; the mobile screenshot was visually inspected. Local browser testing used Chromium 153 from a temporary test-only binary after the standard browser download failed in this environment. GPU was disabled for this restricted runner; browser origin protections remained enabled. CI uses Playwright’s normal Chromium download.

API tests exercise household isolation (including foreign household account/category/transaction/import IDs), CSRF/origin checks, session hashing/expiry, Secure/HttpOnly/SameSite cookies, disabled legacy routes, login throttling, request limits, exact cents, all financial types, split totals/signs, atomic bulk rollback, stale-edit conflicts, imports/reimports/multiplicity/conflicting IDs, signed reconciliation, rollover including overspending/gaps, savings independence, filtering and validation. Tests and browser fixtures use disposable sample databases only.

The test client emits two upstream deprecation warnings for its httpx and AnyIO compatibility paths. They do not affect test outcomes. The development pytest version was updated to 9.0.3 after its advisory check; the final development dependency audit found no known advisories.

## Not executed here

- **Hosted PostgreSQL verification now passed:** PR #2 run 42403258259 completed the full original 31-test suite on PostgreSQL 16, migration upgrade/drift checks, SQLite tests and desktop/mobile browser workflows. See https://github.com/stephenhoover47/PersonalBudgetTracker/actions/runs/42403258259. New staging/bootstrap and Docker checks are added in the follow-up commit; inspect its latest run for their outcome.
- Docker image build/run: no local Docker daemon was available. The follow-up CI job builds the root image, verifies its nonroot user, applies PostgreSQL migrations from the image and checks the running API/frontend/authentication boundary. Its latest CI outcome is the authoritative status.
- Actual iPhone/Safari testing: mobile verification used Chromium at iPhone dimensions. Safari compatibility and touch behavior require a real-device/staging pass.
- Production deployment, real bank credentials, paid APIs, live financial data or legacy-data migration: none performed.

## Readiness

This is an implemented and locally tested MVP, ready for repository review and staging verification. It is not a claim of production certification. Read OPERATIONS.md before deployment, especially CSV identity ambiguities, private two-user authentication/recovery, backup/restore, and the distinction between a spending budget and account cash balances.
