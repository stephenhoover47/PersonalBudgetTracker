import pytest
from household.api import passwords
from household.db import Base
from household.models import Account, Household, User
from household.staging_seed import seed, validate_target
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def configure(monkeypatch):
    monkeypatch.setenv("APP_TIER", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@staging.example/hearth_mvp_staging")
    monkeypatch.setenv("STAGING_DB_HOST", "staging.example")
    monkeypatch.setenv("STAGING_STEPHEN_PASSWORD", "a distinct sample password one")
    monkeypatch.setenv("STAGING_CLAIRE_PASSWORD", "a distinct sample password two")


def test_staging_target_requires_explicit_isolation(monkeypatch):
    configure(monkeypatch)
    url, values = validate_target()
    assert url.database == "hearth_mvp_staging" and len(values) == 2
    for key, value in [
        ("APP_TIER", "production"),
        ("DATABASE_URL", "postgresql://test:test@staging.example/production"),
        ("STAGING_DB_HOST", "another.example"),
        ("RAILWAY_ENVIRONMENT_NAME", "Production"),
        ("STAGING_STEPHEN_PASSWORD", "short"),
    ]:
        with monkeypatch.context() as context:
            context.setenv(key, value)
            with pytest.raises(RuntimeError):
                validate_target()


def test_seed_provisions_two_users_and_never_resets_existing_data(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "seed.db"))
    Base.metadata.create_all(engine)
    values = ["a distinct sample password one", "a distinct sample password two"]
    with Session(engine) as session:
        assert seed(session, values)
        users = session.scalars(select(User).order_by(User.id)).all()
        assert len(users) == 2
        assert all(
            passwords.verify(user.password_hash, value)
            for user, value in zip(users, values, strict=True)
        )
        hashes = [user.password_hash for user in users]
        assert len(session.scalars(select(Account)).all()) == 2
        assert not seed(session, ["replacement password one", "replacement password two"])
        assert [
            user.password_hash for user in session.scalars(select(User).order_by(User.id))
        ] == hashes
        assert len(session.scalars(select(Household)).all()) == 1
    engine.dispose()
