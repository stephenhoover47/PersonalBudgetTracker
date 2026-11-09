import os
import uuid

import pytest
from fastapi.testclient import TestClient
from household.api import create_app, passwords
from household.db import Base
from household.models import Account, Category, Household, User
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture()
def env(tmp_path):
    target = os.getenv("TEST_DATABASE_URL")
    admin = None
    schema = "test_" + uuid.uuid4().hex
    if target:
        url = make_url(target)
        if url.database != "budget_test":
            raise RuntimeError("TEST_DATABASE_URL must target disposable budget_test")
        admin = create_engine(target)
        with admin.begin() as conn:
            conn.execute(text("CREATE SCHEMA " + schema))
        target = url.update_query_dict({"options": "-csearch_path=" + schema}).render_as_string(
            hide_password=False
        )
    app = create_app(target or "sqlite:///" + str(tmp_path / "test.db"), testing=True)
    Base.metadata.create_all(app.state.engine)
    with Session(app.state.engine) as db:
        db.add_all([Household(id=1, name="Together"), Household(id=2, name="Other")])
        db.flush()
        h = passwords.hash("a safe test password")
        db.add_all(
            [
                User(household_id=1, email="one@example.com", name="One", password_hash=h),
                User(household_id=1, email="two@example.com", name="Two", password_hash=h),
                User(household_id=2, email="other@example.com", name="Other", password_hash=h),
            ]
        )
        db.add_all(
            [
                Category(household_id=1, name="Groceries", mode="flexible"),
                Category(household_id=1, name="Dining", mode="flexible"),
                Category(household_id=2, name="Private", mode="fixed"),
                Account(household_id=1, name="Card", kind="credit"),
                Account(household_id=1, name="Checking", kind="checking"),
                Account(household_id=2, name="Other card", kind="credit"),
            ]
        )
        db.commit()
    with TestClient(app) as c:
        c.headers["X-Requested-With"] = "household"
        r = c.post(
            "/api/auth/login", json={"email": "one@example.com", "password": "a safe test password"}
        )
        assert r.status_code == 200, r.text
        c.headers["X-CSRF-Token"] = r.json()["csrf"]
        yield c, app
    app.state.engine.dispose()
    if admin:
        with admin.begin() as conn:
            conn.execute(text("DROP SCHEMA " + schema + " CASCADE"))
        admin.dispose()


def imported(c, csv, account=1):
    r = c.post("/api/imports/preview", json={"account_id": account, "csv": csv})
    assert r.status_code == 200, r.text
    p = r.json()
    r = c.post(f"/api/imports/{p['id']}/commit", json={"expected_net_cents": p["net_cents"]})
    assert r.status_code == 200, r.text
    return r.json()


def items(c, month="2026-11"):
    return c.get("/api/transactions", params={"month": month}).json()["items"]


def classify(c, tx, kind="expense", splits=None):
    return c.put(
        f"/api/transactions/{tx['id']}",
        json={
            "version": tx["version"],
            "kind": kind,
            "splits": splits
            if splits is not None
            else [{"category_id": 1, "cents": tx["cents"]}]
            if kind in {"expense", "loan_payment", "refund", "reimbursement"}
            else [],
        },
    )
