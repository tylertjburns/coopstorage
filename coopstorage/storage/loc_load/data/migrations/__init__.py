"""
Alembic migrations for the SQL schema in sql/tables.py.

Postgres runs these on startup (postgres/db.py init_db). SQLite and the tests use
metadata.create_all instead, the same split as locker's MigrateAsync/EnsureCreated.

To add a migration: edit sql/tables.py, then from the repo root run
`alembic revision --autogenerate -m "<what changed>"` and review the generated script.
"""
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = os.path.dirname(__file__)
BASELINE_REVISION = "0001_baseline"


def alembic_config(engine: Engine) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", MIGRATIONS_DIR)
    cfg.attributes["engine"] = engine
    return cfg


def upgrade(engine: Engine) -> None:
    """
    Bring the database to the latest revision.

    A database created by the earlier create_all-based init_db has the baseline tables
    but no alembic_version table. It is stamped at the baseline first, so the baseline
    doesn't try to create tables that already exist.
    """
    cfg = alembic_config(engine)
    tables = set(inspect(engine).get_table_names())
    if "layouts" in tables and "alembic_version" not in tables:
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")
