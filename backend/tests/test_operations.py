import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from household.api import create_app, passwords
from household.models import Session, User
from sqlalchemy import create_engine, inspect, select, text


def test_migration_is_explicit_repeatable_and_preserves_legacy(tmp_path):
    url = "sqlite:///" + str(tmp_path / "migration.db")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text("CREATE TABLE legacy_sentinel (value TEXT)"))
        db.execute(text("INSERT INTO legacy_sentinel VALUES ('preserve me')"))
    env = {**os.environ, "DATABASE_URL": url}
    cwd = Path(__file__).resolve().parents[1]
    for args in [("upgrade", "head"), ("upgrade", "head"), ("check",)]:
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "household-alembic.ini", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
    assert "hh_users" in inspect(engine).get_table_names()
    with engine.connect() as db:
        assert db.scalar(text("SELECT value FROM legacy_sentinel")) == "preserve me"
    engine.dispose()


def test_session_expiry_and_password_whitespace(env):
    c, app = env
    with app.state.factory() as db:
        user = db.scalar(select(User).where(User.email == "one@example.com"))
        user.password_hash = passwords.hash(" a spaced password ")
        db.commit()
    assert (
        c.post(
            "/api/auth/login", json={"email": "one@example.com", "password": "a spaced password"}
        ).status_code
        == 401
    )
    r = c.post(
        "/api/auth/login", json={"email": " one@example.com ", "password": " a spaced password "}
    )
    assert r.status_code == 200
    assert (
        "httponly" in r.headers["set-cookie"].lower()
        and "samesite=strict" in r.headers["set-cookie"].lower()
    )
    with app.state.factory() as db:
        for auth in db.scalars(select(Session)):
            auth.expires = int(time.time()) - 1
        db.commit()
    assert c.get("/api/me").status_code == 401


def test_large_requests_and_malformed_csv(env):
    c, _ = env
    r = c.post(
        "/api/imports/preview", content=b"x" * 2500001, headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413
    r = c.post(
        "/api/imports/preview",
        json={"account_id": 1, "csv": 'date,merchant,amount\n2026-11-01,"unclosed,1'},
    )
    assert r.status_code == 422


def test_production_requires_https_and_sets_secure_cookie(env, monkeypatch):
    c, original = env
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_ORIGIN", "http://budget.example")
    import pytest

    with pytest.raises(RuntimeError):
        create_app()
    monkeypatch.setenv("APP_ORIGIN", "https://budget.example")
    app = create_app(original.state.engine.url.render_as_string(hide_password=False))
    with TestClient(app, base_url="https://budget.example") as client:
        r = client.post(
            "/api/auth/login",
            headers={"X-Requested-With": "household"},
            json={"email": "one@example.com", "password": "a safe test password"},
        )
        assert r.status_code == 200
        assert "secure" in r.headers["set-cookie"].lower()
        assert client.get("/api/me").status_code == 200
        assert client.get("/docs").status_code == 404
        assert client.get("/health").headers["strict-transport-security"] == "max-age=31536000"
    app.state.engine.dispose()
