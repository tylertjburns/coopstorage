import logging
from typing import Dict, List, Optional

from coopstorage.location_map_tree import LocationMapTree
from coopstorage.storage.loc_load.data.layout_data_store import (
    LayoutDataStore, LayoutRecord, LocationDataStoreFactory,
)
from coopstorage.storage.loc_load.data.storageDataStore import StorageDataStore
from coopstorage.storage.loc_load.storage import Storage

logger = logging.getLogger(__name__)


class LayoutManager:
    """
    Registry of Storage instances, one per layout_id.

    Backend-agnostic by injection: pass a LayoutDataStore and a factory that
    builds a per-layout location DataStoreProtocol. LayoutManager itself never
    imports a concrete backend. Use postgres_layout_manager() or
    sqlite_layout_manager() for the standard SQL-backed factories.
    """

    def __init__(
        self,
        layout_data_store: LayoutDataStore,
        location_data_store_factory: LocationDataStoreFactory,
    ):
        self._layout_data_store = layout_data_store
        self._location_data_store_factory = location_data_store_factory
        self._instances: Dict[str, Storage] = {}

    # ── Storage registry ──────────────────────────────────────────────────────

    def get_storage(self, layout_id: str) -> Storage:
        key = str(layout_id)
        if key not in self._instances:
            self._instances[key] = self._create_storage(key)
        return self._instances[key]

    def _create_storage(self, layout_id: str) -> Storage:
        loc_store = self._location_data_store_factory(layout_id)
        data_store = StorageDataStore(location_data_store=loc_store)
        tree = LocationMapTree()

        locs_data = data_store.LocationsData
        if locs_data.supports_tree_labels:
            for loc_id in locs_data.get().keys():
                labels = locs_data.get_tree_labels(loc_id)
                if labels:
                    tree.register(loc_id, **labels)

        storage = Storage(
            data_store=data_store,
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
    from coopstorage.storage.loc_load.data.sql.sql_layout_data_store import SqlLayoutDataStore
    from coopstorage.storage.loc_load.data.sql.sql_location_data_store import SqlLocationDataStore

    init_db()
    return LayoutManager(
        layout_data_store=SqlLayoutDataStore(get_session),
        location_data_store_factory=lambda layout_id: SqlLocationDataStore(layout_id, get_session),
    )


def sqlite_layout_manager(url: str = None) -> LayoutManager:
    """Return a LayoutManager backed by SQLite. Defaults to coopstorage_dev.db."""
    from coopstorage.storage.loc_load.data.sqlite import db as sqlite_db
    from coopstorage.storage.loc_load.data.sql.sql_layout_data_store import SqlLayoutDataStore
    from coopstorage.storage.loc_load.data.sql.sql_location_data_store import SqlLocationDataStore

    if url:
        sqlite_db.set_url(url)
    sqlite_db.init_db()
    return LayoutManager(
        layout_data_store=SqlLayoutDataStore(sqlite_db.get_session),
        location_data_store_factory=lambda layout_id: SqlLocationDataStore(layout_id, sqlite_db.get_session),
    )
