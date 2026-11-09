"""Local administrative provisioning; never accepts passwords on the command line."""

import argparse
import getpass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from .api import passwords
from .db import database_url, make_engine
from .models import Category, Household, Session, User


def password():
    value = getpass.getpass("Password (12+ characters): ")
    if len(value) < 12 or len(value) > 200 or value != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords must match and contain 12–200 characters")
    return passwords.hash(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init-household", "reset-password"])
    args = parser.parse_args()
    with DBSession(make_engine(database_url())) as db:
        if args.command == "init-household":
            if db.scalar(select(Household.id)):
                raise SystemExit("Household already exists. No records changed.")
            household = Household(name=input("Household name: ").strip()[:100] or "Our household")
            db.add(household)
            db.flush()
            for i in range(2):
                print(f"Member {i + 1}")
                email = input("Email: ").strip().casefold()
                if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
                    raise SystemExit("Invalid email")
                name = input("Display name: ").strip()[:100]
                if not name:
                    raise SystemExit("Display name required")
                db.add(
                    User(
                        household_id=household.id, email=email, name=name, password_hash=password()
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
                db.add(Category(household_id=household.id, name=name, mode=mode))
        else:
            user = db.scalar(select(User).where(User.email == input("Email: ").strip().casefold()))
            if not user:
                raise SystemExit("User not found")
            user.password_hash = password()
            for auth in db.scalars(select(Session).where(Session.user_id == user.id)):
                db.delete(auth)
        db.commit()
        print("Saved.")


if __name__ == "__main__":
    main()
