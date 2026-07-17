import logging
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

_url: str = None
_engine = None
_SessionFactory = None


def set_url(url: str):
    """Override the SQLite URL and reset cached engine/session factory."""
    global _url, _engine, _SessionFactory
    _url = url
    _engine = None
    _SessionFactory = None


def get_sqlite_url() -> str:
    return _url or os.environ.get('SQLITE_URL', 'sqlite:///./coopstorage_dev.db')


def is_configured() -> bool:
    return True


def get_engine():
    global _engine
    if _engine is None:
        url = get_sqlite_url()
        _engine = create_engine(url, connect_args={'check_same_thread': False})
        if ':memory:' not in url:
            @event.listens_for(_engine, 'connect')
            def _set_wal(dbapi_conn, connection_record):
                dbapi_conn.execute('PRAGMA journal_mode=WAL')
        logger.info("SQLite engine created: %s", url)
    return _engine


def init_db():
    from coopstorage.storage.loc_load.data.sql.tables import metadata
    metadata.create_all(get_engine())
    logger.info("SQLite schema initialised")


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
