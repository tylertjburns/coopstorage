import logging
from typing import Dict, Iterable, Optional

from coopmongo.mongoCollectionDataStore import MongoCollectionDataStore, ObjectDocumentFacade
from cooptools.protocols import UniqueIdentifier
from cooptools.qualifiers import PatternMatchQualifier

from coopstorage.storage.loc_load.location import Location
from .mongo_connection import mongo_connection_args

logger = logging.getLogger(__name__)


class MongoLocationDataStore:
    """
    DataStoreProtocol implementation for Location objects backed by MongoDB.

    Each layout gets its own collection named locations_<layout_id>.
    Tree labels are held in an in-process cache only; they are not persisted
    to Mongo and will be empty after a process restart.
    """

    def __init__(
        self,
        layout_id: str,
        db_name: str = 'storage',
        connection_args=None,
    ):
        self._layout_id = str(layout_id)
        collection_name = f"locations_{self._layout_id.replace('-', '_')}"
        facade = ObjectDocumentFacade(
            obj_to_doc_translator=Location.to_jsonable_dict,
            doc_to_obj_translator=Location.from_jsonable_dict,
        )
        self._store = MongoCollectionDataStore(
            db_name=db_name,
            collection_name=collection_name,
            connection_args=connection_args or mongo_connection_args(),
            facade=facade,
        )
        self._tree_cache: Dict[str, Dict] = {}

    # ── DataStoreProtocol ─────────────────────────────────────────────────────

    def add(self, items: Iterable[Location]) -> 'MongoLocationDataStore':
        self._store.add(list(items))
        return self

    def update(self, items: Iterable[Location]) -> 'MongoLocationDataStore':
        self._store.update(list(items))
        return self

    def add_or_update(self, items: Iterable[Location]) -> 'MongoLocationDataStore':
        self._store.add_or_update(list(items))
        return self

    def remove(
        self,
        items: Iterable[Location] = None,
        cursor_range=None,
        ids: Iterable[UniqueIdentifier] = None,
    ) -> 'MongoLocationDataStore':
        if ids is not None:
            self._store.remove(ids=list(ids))
        elif items is not None:
            self._store.remove(items=list(items))
        return self

    def get(
        self,
        cursor_range=None,
        ids: Iterable[UniqueIdentifier] = None,
        limit: int = None,
        query: Dict = None,
        id_query: PatternMatchQualifier = None,
    ) -> Dict[UniqueIdentifier, Location]:
        result = self._store.get(ids=ids, limit=limit)
        if id_query is not None:
            qual = id_query.qualify(list(result.keys()))
            result = {k: v for k, v in result.items() if qual.get(str(k), type('_r', (), {'result': False})()).result}
        return result

    def iter_values(self) -> Iterable[Location]:
        return list(self._store.get().values())

    def count(self) -> int:
        return self._store.count()

    def clear(self) -> 'MongoLocationDataStore':
        self._store.clear()
        self._tree_cache.clear()
        return self

    def __contains__(self, item) -> bool:
        item_id = str(item.Id) if hasattr(item, 'Id') else str(item)
        return bool(self._store.get(ids=[item_id]))

    # ── Tree-label helpers (in-memory only) ───────────────────────────────────

    def get_tree_labels(self, loc_id: str) -> Dict:
        return dict(self._tree_cache.get(str(loc_id), {}))

    def upsert_tree_labels(self, loc_id: str, tree_labels: Dict):
        self._tree_cache[str(loc_id)] = dict(tree_labels)
