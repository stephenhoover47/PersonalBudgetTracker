from alembic import context
from household import models  # noqa: F401 -- register ORM metadata
from household.db import Base, database_url, make_engine

config = context.config


def include_name(name, type_, parent_names):
    # Alembic must never propose dropping unrelated legacy/extension tables.
    return type_ != "table" or name.startswith("hh_")


if context.is_offline_mode():
    context.configure(
        url=database_url(),
        target_metadata=Base.metadata,
        literal_binds=True,
        version_table="hh_alembic_version",
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with make_engine(database_url()).connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            version_table="hh_alembic_version",
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()
