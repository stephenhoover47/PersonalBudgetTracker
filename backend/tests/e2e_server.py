"""Disposable local browser-test server. Never reads DATABASE_URL."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from household.api import create_app, passwords
from household.db import Base
from household.models import Category, Household, User

with tempfile.TemporaryDirectory(prefix="pbt-e2e-") as directory:
    os.environ["APP_ORIGIN"] = "http://127.0.0.1:8765"
    app = create_app("sqlite:///" + str(Path(directory) / "e2e.db"), testing=True)
    Base.metadata.create_all(app.state.engine)
    with app.state.factory() as db:
        db.add(Household(id=1, name="Our household"))
        db.flush()
        for email, name in [("one@example.com", "Stephen"), ("two@example.com", "Claire")]:
            db.add(
                User(
                    household_id=1,
                    email=email,
                    name=name,
                    password_hash=passwords.hash("sample test password"),
                )
            )
        db.add_all(
            [
                Category(household_id=1, name="Groceries", mode="flexible"),
                Category(household_id=1, name="Dining", mode="flexible"),
            ]
        )
        db.commit()
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
