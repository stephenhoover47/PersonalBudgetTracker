# Household backend

The active application is `app.main:app`, which mounts only the authenticated `household` package. See the [root README](../README.md) for setup, migrations, two-user provisioning and tests, and [operations](../docs/OPERATIONS.md) for production preparation.

Run migrations explicitly with `alembic -c household-alembic.ini upgrade head`; use `python -m household.cli init-household` to provision two users. Do not run the legacy `scripts/` setup, seed or Plaid sync workflows. The legacy API, db and Plaid modules remain as unmounted reference; they are not the current schema or service implementation.

`backend/Dockerfile` builds a backend-only service. The root Dockerfile builds the recommended same-origin application including the frontend. No automatic deployment or production schema/data change is part of this branch.
