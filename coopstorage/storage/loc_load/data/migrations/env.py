import os

from alembic import context
from sqlalchemy import create_engine

from coopstorage.storage.loc_load.data.sql.tables import metadata

config = context.config


def _engine():
    engine = config.attributes.get("engine")
    if engine is not None:
        return engine
    # CLI use (alembic revision --autogenerate): the same env vars the app reads.
    url = os.environ.get("DATABASE_URL") or os.environ.get("SQLITE_URL", "sqlite:///./coopstorage_dev.db")
    return create_engine(url)


if context.is_offline_mode():
    raise RuntimeError("Offline (--sql) migrations are not supported; run against a database")

with _engine().connect() as connection:
    # Batch mode lets ALTERs work on SQLite, which can't alter most constraints in place.
    context.configure(connection=connection, target_metadata=metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
