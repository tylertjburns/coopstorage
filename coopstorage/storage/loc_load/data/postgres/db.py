import logging
import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .tables import metadata

logger = logging.getLogger(__name__)

_engine = None
_SessionFactory = None


def is_configured() -> bool:
    """Return True if DATABASE_URL is present in the environment."""
    return bool(os.environ.get('DATABASE_URL'))


def get_engine():
    global _engine
    if _engine is None:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set. "
                "Set it to a PostgreSQL connection string to enable Postgres persistence."
            )
        _engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        logger.info("Postgres engine created")
    return _engine


def init_db():
    """Create all tables that do not yet exist. Safe to call on every startup."""
    metadata.create_all(get_engine())
    logger.info("Postgres schema initialised")


@contextmanager
def get_session():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
