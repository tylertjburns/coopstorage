import logging
from typing import Dict, List, Optional

from coopstorage.location_map_tree import LocationMapTree
from coopstorage.storage.loc_load.data.sql.sql_layout_data_store import SqlLayoutDataStore, LayoutRecord
from coopstorage.storage.loc_load.data.sql.sql_location_data_store import SqlLocationDataStore
from coopstorage.storage.loc_load.data.storageDataStore import StorageDataStore
from coopstorage.storage.loc_load.storage import Storage

logger = logging.getLogger(__name__)


class LayoutManager:
    """
    Registry of Storage instances, one per layout_id.

    Backend-agnostic: pass any session_factory whose context manager yields a
    SQLAlchemy Session (same contract as get_session() in the db modules).
    Use the factory helpers postgres_layout_manager() or sqlite_layout_manager()
    for the standard backends, or wire your own session_factory for custom setups.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._layout_data_store = SqlLayoutDataStore(session_factory)
        self._instances: Dict[str, Storage] = {}

    # ── Storage registry ──────────────────────────────────────────────────────

    def get_storage(self, layout_id: str) -> Storage:
        key = str(layout_id)
        if key not in self._instances:
            self._instances[key] = self._create_storage(key)
        return self._instances[key]

    def _create_storage(self, layout_id: str) -> Storage:
        loc_store = SqlLocationDataStore(layout_id, self._session_factory)
        tree = LocationMapTree()

        loc_store._ensure_cache()
        for loc_id, labels in loc_store._tree_cache.items():
            if labels:
                tree.register(loc_id, **labels)

        storage = Storage(
            data_store=StorageDataStore(location_data_store=loc_store),
            location_map_tree=tree,
        )
        logger.info("Created Storage instance for layout %s (%d locations)",
                    layout_id, loc_store.count())
        return storage

    def evict(self, layout_id: str):
        """Remove a cached Storage instance (e.g. after layout deletion)."""
        self._instances.pop(str(layout_id), None)

    # ── Layout CRUD ───────────────────────────────────────────────────────────

    def create_layout(self, name: str, description: Optional[str] = None) -> LayoutRecord:
        return self._layout_data_store.create(name, description)

    def list_layouts(self) -> List[LayoutRecord]:
        return self._layout_data_store.get_all()

    def get_layout(self, layout_id) -> Optional[LayoutRecord]:
        return self._layout_data_store.get(layout_id)

    def update_layout(
        self,
        layout_id,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[LayoutRecord]:
        return self._layout_data_store.update(layout_id, name, description)

    def delete_layout(self, layout_id) -> None:
        self.evict(layout_id)
        self._layout_data_store.delete(layout_id)


def postgres_layout_manager() -> LayoutManager:
    """Return a LayoutManager backed by Postgres (DATABASE_URL must be set)."""
    from coopstorage.storage.loc_load.data.postgres.db import get_session, init_db
    init_db()
    return LayoutManager(get_session)


def sqlite_layout_manager(url: str = None) -> LayoutManager:
    """Return a LayoutManager backed by SQLite. Defaults to coopstorage_dev.db."""
    from coopstorage.storage.loc_load.data.sqlite import db as sqlite_db
    if url:
        sqlite_db.set_url(url)
    sqlite_db.init_db()
    return LayoutManager(sqlite_db.get_session)
