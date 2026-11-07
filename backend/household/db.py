import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def make_engine(url):
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(
        url,
        pool_pre_ping=True,
        **({"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}),
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def foreign_keys(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")

    return engine


def database_url():
    return os.environ.get("DATABASE_URL", "sqlite:///./household.db")
