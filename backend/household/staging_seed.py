"""One-time sample household provisioning for the isolated MVP staging database.

Never runs during normal application startup. The deploy command must opt in;
existing households/passwords are never overwritten.
"""

import os

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from .api import passwords
from .db import make_engine
from .models import Account, Category, Household, User


def validate_target():
    if os.getenv("APP_TIER") != "staging":
        raise RuntimeError("Sample provisioning requires APP_TIER=staging")
    if os.getenv("RAILWAY_ENVIRONMENT_NAME", "staging").casefold() not in {"sandbox", "staging"}:
        raise RuntimeError("Sample provisioning refuses this deployment environment")
    url = make_url(os.environ["DATABASE_URL"])
    if url.get_backend_name() != "postgresql" or url.database != "hearth_mvp_staging":
        raise RuntimeError("Sample provisioning requires the dedicated hearth_mvp_staging database")
    expected_host = os.getenv("STAGING_DB_HOST")
    if not expected_host or url.host != expected_host:
        raise RuntimeError("Sample provisioning database host does not match the staging allowlist")
    values = [os.getenv("STAGING_STEPHEN_PASSWORD", ""), os.getenv("STAGING_CLAIRE_PASSWORD", "")]
    if any(len(value) < 16 or len(value) > 200 for value in values) or values[0] == values[1]:
        raise RuntimeError("Two distinct staging passwords of 16–200 characters are required")
    return url, values


def seed(session, member_passwords):
    # Idempotent: never reset credentials or add demo data to an existing household.
    if session.scalar(select(Household.id).limit(1)) is not None:
        return False
    household = Household(name="Stephen & Claire · Staging")
    session.add(household)
    session.flush()
    for name, email, password in zip(
        ["Stephen", "Claire"],
        ["stephen@example.test", "claire@example.test"],
        member_passwords,
        strict=True,
    ):
        session.add(
            User(
                household_id=household.id,
                name=name,
                email=email,
                password_hash=passwords.hash(password),
            )
        )
    for name, mode in [
        ("Housing", "fixed"),
        ("Utilities", "fixed"),
        ("Groceries", "flexible"),
        ("Dining & dates", "flexible"),
        ("Transport", "flexible"),
        ("Household", "flexible"),
        ("Loan payments", "fixed"),
    ]:
        session.add(Category(household_id=household.id, name=name, mode=mode))
    session.add_all(
        [
            Account(household_id=household.id, name="Sample shared card", kind="credit"),
            Account(household_id=household.id, name="Sample joint checking", kind="checking"),
        ]
    )
    session.commit()
    return True


def main():
    url, values = validate_target()
    engine = make_engine(url)
    try:
        with Session(engine) as session:
            created = seed(session, values)
        print(
            "Staging sample household provisioned."
            if created
            else "Existing household left unchanged."
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
