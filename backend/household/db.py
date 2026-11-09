import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def make_engine(url):
    url = make_url(url)
    if url.drivername == "postgres":
        url = url.set(drivername="postgresql")
    is_sqlite = url.get_backend_name() == "sqlite"
    engine = create_engine(
        url,
        pool_pre_ping=True,
        **({"connect_args": {"check_same_thread": False}} if is_sqlite else {}),
    )
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def foreign_keys(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")

    return engine


def database_url():
    return os.environ.get("DATABASE_URL", "sqlite:///./household.db")
