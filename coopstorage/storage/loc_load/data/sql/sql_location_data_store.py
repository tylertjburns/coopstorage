import logging
import uuid
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy import text as sa_text

import coopstorage.storage.loc_load.dcs as dcs
from coopstorage.storage.loc_load.location import Location
from cooptools.protocols import UniqueIdentifier
from cooptools.qualifiers import PatternMatchQualifier

from .tables import channels as chan_table, locations as loc_table

logger = logging.getLogger(__name__)

_TREE_LABEL_COLS = ('zone', 'aisle', 'row', 'bay', 'shelf')


class SqlLocationDataStore:
    """
    DataStoreProtocol implementation for Location objects backed by any SQL database.

    Scoped to one layout_id.  All locations are held in an in-process cache;
    lazily populated on first read and invalidated on structural writes.
    Channel-state updates (slot mutations) use targeted in-place cache refreshes
    to keep the transfer path fast.

    session_factory: a zero-argument callable that returns a context manager
    yielding a SQLAlchemy Session (same signature as get_session() in db modules).
    """

    def __init__(self, layout_id: str, session_factory):
        self._layout_id = uuid.UUID(str(layout_id))
        self._session_factory = session_factory
        self._loc_cache: Dict[str, Location] = {}
        self._tree_cache: Dict[str, Dict] = {}
        self._cache_valid = False

    # ── Cache management ──────────────────────────────────────────────────────

    def _invalidate_cache(self):
        self._loc_cache.clear()
        self._tree_cache.clear()
        self._cache_valid = False

    def _ensure_cache(self):
        if not self._cache_valid:
            self._loc_cache, self._tree_cache = self._load_all_from_db()
            self._cache_valid = True

    def _load_all_from_db(self) -> Tuple[Dict[str, Location], Dict[str, Dict]]:
        with self._session_factory() as sess:
            stmt = (
                select(loc_table, chan_table)
                .join(chan_table, loc_table.c.channel_id == chan_table.c.id)
                .where(loc_table.c.layout_id == self._layout_id)
            )
            rows = sess.execute(stmt).fetchall()
        locs: Dict[str, Location] = {}
        trees: Dict[str, Dict] = {}
        for row in rows:
            loc = self._row_to_location(row)
            locs[str(loc.Id)] = loc
            trees[str(loc.Id)] = self._row_to_tree_labels(row)
        return locs, trees

    # ── Row ↔ domain conversion ───────────────────────────────────────────────

    @staticmethod
    def _row_to_location(row) -> Location:
        channel_state: Dict[int, str] = {}
        for i, cid in enumerate(row.slots or []):
            if cid is not None:
                channel_state[i] = cid
        meta = dcs.LocationMeta(
            dims=(row.dim_x, row.dim_y, row.dim_z),
            channel_processor=row.processor_type,
            capacity=row.capacity,
            channel_axis=row.channel_axis,
            delete_on_receive=row.delete_on_receive,
        )
        return Location(
            id=row.id,
            location_meta=meta,
            coords=(row.x, row.y, row.z),
            channel_state=channel_state or None,
        )

    @staticmethod
    def _row_to_tree_labels(row) -> Dict:
        labels = {}
        for col in _TREE_LABEL_COLS:
            val = getattr(row, col, None)
            if val is not None:
                labels[col] = val
        extra = getattr(row, 'extra_labels', None) or {}
        labels.update(extra)
        return labels

    def _location_to_rows(self, loc: Location, existing_channel_id=None) -> Tuple[dict, dict]:
        channel_id = existing_channel_id if existing_channel_id is not None else uuid.uuid4()
        channel_row = {
            'id': channel_id,
            'processor_type': type(loc.Meta.channel_processor).__name__,
            'capacity': loc.Capacity,
            'channel_axis': loc.Meta.channel_axis,
            'slots': loc.Slots,
        }
        loc_row = {
            'id': str(loc.Id),
            'layout_id': self._layout_id,
            'x': loc.Coords[0], 'y': loc.Coords[1], 'z': loc.Coords[2],
            'dim_x': loc.Meta.dims[0], 'dim_y': loc.Meta.dims[1], 'dim_z': loc.Meta.dims[2],
            'delete_on_receive': loc.Meta.delete_on_receive,
            'channel_id': channel_id,
        }
        return loc_row, channel_row

    # ── DataStoreProtocol ─────────────────────────────────────────────────────

    def add(self, items: Iterable[Location]) -> 'SqlLocationDataStore':
        items_list = list(items)
        if not items_list:
            return self
        with self._session_factory() as sess:
            for loc in items_list:
                loc_row, chan_row = self._location_to_rows(loc)
                sess.execute(insert(chan_table).values(**chan_row))
                sess.execute(insert(loc_table).values(**loc_row))
        self._invalidate_cache()
        return self

    def update(self, items: Iterable[Location]) -> 'SqlLocationDataStore':
        """
        On the transfer hot-path only channel slots change; loc_table rows are
        static.  Updates only channels.slots and does a targeted in-place cache
        refresh instead of a full reload.
        """
        items_list = list(items)
        if not items_list:
            return self
        with self._session_factory() as sess:
            for loc in items_list:
                row = sess.execute(
                    select(loc_table.c.channel_id).where(and_(
                        loc_table.c.id == str(loc.Id),
                        loc_table.c.layout_id == self._layout_id,
                    ))
                ).fetchone()
                if row is None:
                    logger.warning(
                        "update: location %s not found in layout %s — skipping",
                        loc.Id, self._layout_id,
                    )
                    continue
                sess.execute(
                    update(chan_table)
                    .where(chan_table.c.id == row.channel_id)
                    .values(slots=loc.Slots, updated_at=sa_text('CURRENT_TIMESTAMP'))
                )
        if self._cache_valid:
            for loc in items_list:
                self._loc_cache[str(loc.Id)] = loc
        return self

    def add_or_update(self, items: Iterable[Location]) -> 'SqlLocationDataStore':
        items_list = list(items)
        if not items_list:
            return self
        inserted_any = False
        with self._session_factory() as sess:
            for loc in items_list:
                row = sess.execute(
                    select(loc_table.c.channel_id).where(and_(
                        loc_table.c.id == str(loc.Id),
                        loc_table.c.layout_id == self._layout_id,
                    ))
                ).fetchone()
                if row is not None:
                    sess.execute(
                        update(chan_table)
                        .where(chan_table.c.id == row.channel_id)
                        .values(slots=loc.Slots, updated_at=sa_text('CURRENT_TIMESTAMP'))
                    )
                else:
                    loc_row, chan_row = self._location_to_rows(loc)
                    sess.execute(insert(chan_table).values(**chan_row))
                    sess.execute(insert(loc_table).values(**loc_row))
                    inserted_any = True
        if inserted_any:
            self._invalidate_cache()
        elif self._cache_valid:
            for loc in items_list:
                self._loc_cache[str(loc.Id)] = loc
        return self

    def remove(
        self,
        items: Iterable[Location] = None,
        cursor_range=None,
        ids: Iterable[UniqueIdentifier] = None,
    ) -> 'SqlLocationDataStore':
        target_ids: List[str] = []
        if items is not None:
            target_ids += [str(loc.Id) for loc in items]
        if ids is not None:
            target_ids += [str(i) for i in ids]
        if not target_ids:
            return self
        with self._session_factory() as sess:
            chan_ids = sess.execute(
                select(loc_table.c.channel_id).where(and_(
                    loc_table.c.id.in_(target_ids),
                    loc_table.c.layout_id == self._layout_id,
                ))
            ).scalars().all()
            sess.execute(
                delete(loc_table).where(and_(
                    loc_table.c.id.in_(target_ids),
                    loc_table.c.layout_id == self._layout_id,
                ))
            )
            if chan_ids:
                sess.execute(delete(chan_table).where(chan_table.c.id.in_(list(chan_ids))))
        self._invalidate_cache()
        return self

    def get(
        self,
        cursor_range=None,
        ids: Iterable[UniqueIdentifier] = None,
        limit: int = None,
        query: Dict = None,
        id_query: PatternMatchQualifier = None,
    ) -> Dict[UniqueIdentifier, Location]:
        self._ensure_cache()
        result: Dict[str, Location] = dict(self._loc_cache)

        if ids is not None:
            id_set = {str(i) for i in ids}
            result = {k: v for k, v in result.items() if str(k) in id_set}

        if id_query is not None:
            qual = id_query.qualify(list(result.keys()))
            result = {k: v for k, v in result.items() if qual.get(str(k), type('_r', (), {'result': False})()).result}

        if limit is not None:
            result = dict(list(result.items())[:limit])

        return result

    def iter_values(self) -> Iterable[Location]:
        self._ensure_cache()
        return list(self._loc_cache.values())

    def count(self) -> int:
        self._ensure_cache()
        return len(self._loc_cache)

    def clear(self) -> 'SqlLocationDataStore':
        with self._session_factory() as sess:
            chan_ids = sess.execute(
                select(loc_table.c.channel_id).where(
                    loc_table.c.layout_id == self._layout_id
                )
            ).scalars().all()
            sess.execute(delete(loc_table).where(loc_table.c.layout_id == self._layout_id))
            if chan_ids:
                sess.execute(delete(chan_table).where(chan_table.c.id.in_(list(chan_ids))))
        self._invalidate_cache()
        return self

    def __contains__(self, item) -> bool:
        self._ensure_cache()
        item_id = str(item.Id) if hasattr(item, 'Id') else str(item)
        return item_id in self._loc_cache

    # ── Tree-label helpers ────────────────────────────────────────────────────

    def get_tree_labels(self, loc_id: str) -> Dict:
        self._ensure_cache()
        return dict(self._tree_cache.get(str(loc_id), {}))

    def upsert_tree_labels(self, loc_id: str, tree_labels: Dict):
        std_keys = set(_TREE_LABEL_COLS)
        standard = {k: v for k, v in tree_labels.items() if k in std_keys}
        extra = {k: v for k, v in tree_labels.items() if k not in std_keys} or None

        vals = {**standard}
        if extra is not None:
            vals['extra_labels'] = extra

        with self._session_factory() as sess:
            sess.execute(
                update(loc_table)
                .where(and_(
                    loc_table.c.id == loc_id,
                    loc_table.c.layout_id == self._layout_id,
                ))
                .values(**vals)
            )
        if self._cache_valid:
            self._tree_cache[str(loc_id)] = dict(tree_labels)
