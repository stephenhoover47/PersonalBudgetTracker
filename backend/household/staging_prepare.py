"""Run the guarded staging migration and sample-account setup as one deploy command."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from . import staging_seed


def main():
    staging_seed.validate_target()  # Reject non-staging targets before any schema writes.
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "household-alembic.ini"))
    config.set_main_option("script_location", str(root / "household_migrations"))
    command.upgrade(config, "head")
    staging_seed.main()


if __name__ == "__main__":
    main()
