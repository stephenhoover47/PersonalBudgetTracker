# Hearth — PersonalBudgetTracker

A mobile-friendly household budget for two people with separate logins. Shared accounts only; personal spending stays separate. FastAPI + SQLAlchemy + PostgreSQL, React + TypeScript. CSV first; no Plaid subscription or bank credentials required.

## Start locally

Requires Python 3.12+ and Node 22.12+ (Node 24 recommended). From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
export DATABASE_URL=sqlite:///./household.db
alembic -c household-alembic.ini upgrade head
python -m household.cli init-household
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The CLI prompts for exactly two members and hidden passwords (12+ characters). On Windows cmd.exe, activate with `.venv\Scripts\activate`, and use `set DATABASE_URL=sqlite:///./household.db` instead of `export`. Do not use a production database for local development.

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8000. Add joint checking/shared credit cards in Settings, import posted CSV transactions, classify them, and set this month’s category budgets in Plan. Use `samples/household.csv` for a fictional example.

To serve one origin from FastAPI:

```bash
cd frontend
npm run build
cd ../backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Set `APP_ORIGIN=http://localhost:8000` for browser requests to this origin. Never expose the development server publicly.

## Financial behavior

- Integer USD cents. Positive = money out; negative = money in. No floating-point money in storage or calculations.
- Purchases and loan payments consume category budgets. Credit card payments, owned-account transfers, and savings transfers do not.
- Refunds/reimbursements reduce spending in the category and month received. Income and household contributions have separate totals.
- Every imported row starts as **Needs review** and is excluded from spending until classified. The dashboard explicitly warns when totals are incomplete.
- Category splits must exactly equal the transaction and use the same sign. Bulk edits are atomic; concurrent stale transaction edits return 409.
- Each month has explicit category budgets. Copy the previous month to start a new plan. Rollover carries positive or negative remainder through consecutive configured months when rollover is enabled; gaps/resetting rollover break the chain. Historical edits intentionally recalculate later carry.
- Savings allocations are monthly planning earmarks, separate from spending budget remainder. They never move money. Reuse a goal’s name to update it; set $0 to clear the allocation.

## CSV and reconciliation

Standard headers: `date,merchant,amount,external_id` (`external_id` optional). Dates are YYYY-MM-DD or MM/DD/YYYY. The UI includes amount-sign selection for standard CSV, a Chase adapter (negative purchases), and a Capital One adapter (positive Debit/Credit columns). These adapters use posted **Transaction Date**, not pending activity. Only import USD exports. Preview the normalized signs before committing.

The preview reports existing rows, new net outflow and the full file net. You must confirm the signed file net in dollars; any mismatch prevents all writes. Commit rechecks duplicates within a household-level write lock, then inserts atomically. An import can commit only once; previews expire after 24 hours.

Stable external IDs are preferred. Conflicting amount/date changes for an existing ID stop the import for investigation. Without IDs, duplicate identity is account + posted date + normalized merchant + amount + occurrence number, preserving repeated same-day purchases. **Partial-day files, altered merchant descriptions or changed amounts can be ambiguous without bank IDs.** Use overlapping complete-day exports, inspect the preview, and reconcile the source statement. This is file-total reconciliation, not a full opening/closing bank-balance ledger. Do not import the same shared card twice under different account records.

## Verification

```bash
cd backend
python -m pytest tests -q
alembic -c household-alembic.ini check
cd ../frontend
npm test
npm run build
npm run test:e2e
```

Browser tests require `npx playwright install --with-deps chromium`, a built frontend, and a temporary seeded backend started by the Playwright configuration. They never use live accounts. CI also runs migrations and smoke tests against disposable PostgreSQL 16, plus SQLite API tests. See [docs/VALIDATION.md](docs/VALIDATION.md) for actual local results and limits.

## Production preparation — no deployment performed

See [docs/OPERATIONS.md](docs/OPERATIONS.md) for the migration and deployment checklist, password recovery, backups and operational limits. Use the root Dockerfile for a single-origin image. It runs as an unprivileged user and does **not** migrate or seed on startup. `backend/Dockerfile` remains backend-only; the root Dockerfile includes the frontend.

The old unauthenticated Plaid/analytics files are retained as unmounted reference only. No legacy tokens are read or exposed. New `hh_*` tables and `hh_alembic_version` leave legacy tables untouched. Do not run legacy setup/sync/sample scripts against this MVP. No automatic migration of old financial data is attempted. See [docs/AUDIT.md](docs/AUDIT.md).
