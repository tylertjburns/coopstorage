import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from pubsub import pub

from coopstorage.enums import StorageTopic
from coopstorage.storage.loc_load.storage import Storage


@dataclass
class HeatmapRecord:
    location_id:  str
    record_type:  str            # 'location' | 'load'
    entry_time:   datetime
    expiry_time:  Optional[datetime] = None
    container_id: Optional[str] = None   # set for 'load' records


class HeatmapTracker:
    """
    Subscribes to PyPubSub reservation events and accumulates time-stamped
    records per location.  Records carry both entry and expiry times so
    callers can query for reservations that occurred in any time window.
    """

    def __init__(self, storage: Storage):
        self._storage = storage
        self._records: list[HeatmapRecord] = []
        self._lock = threading.Lock()

        pub.subscribe(self._on_container_reserved,   StorageTopic.CONTAINER_RESERVED.value)
        pub.subscribe(self._on_container_unreserved, StorageTopic.CONTAINER_UNRESERVED.value)
        pub.subscribe(self._on_location_reserved,    StorageTopic.LOCATION_RESERVED.value)
        pub.subscribe(self._on_location_unreserved,  StorageTopic.LOCATION_UNRESERVED.value)

    # ── pypubsub handlers ─────────────────────────────────────────────────────

    def _on_container_reserved(self, payload):
        cid    = str(payload.get('container_id', ''))
        loc_id = self._find_container_location(cid)
        if loc_id is None:
            return
        with self._lock:
            self._records.append(HeatmapRecord(
                location_id=loc_id,
                record_type='load',
                entry_time=datetime.now(timezone.utc),
                container_id=cid,
            ))

    def _on_container_unreserved(self, payload):
        cid = str(payload.get('container_id', ''))
        now = datetime.now(timezone.utc)
        with self._lock:
            for rec in reversed(self._records):
                if rec.record_type == 'load' and rec.container_id == cid and rec.expiry_time is None:
                    rec.expiry_time = now
                    break

    def _on_location_reserved(self, payload):
        lid = str(payload.get('location_id', ''))
        if not lid:
            return
        with self._lock:
            self._records.append(HeatmapRecord(
                location_id=lid,
                record_type='location',
                entry_time=datetime.now(timezone.utc),
            ))

    def _on_location_unreserved(self, payload):
        lid = str(payload.get('location_id', ''))
        now = datetime.now(timezone.utc)
        with self._lock:
            for rec in reversed(self._records):
                if rec.record_type == 'location' and rec.location_id == lid and rec.expiry_time is None:
                    rec.expiry_time = now
                    break

    # ── query ─────────────────────────────────────────────────────────────────

    def get_counts(
        self,
        start: Optional[datetime] = None,
        end:   Optional[datetime] = None,
    ) -> dict:
        """
        Return per-location reservation counts, optionally filtered by the
        entry_time of each record.  Both bounds are inclusive; omit either
        to leave that end open.
        """
        with self._lock:
            records = list(self._records)

        location_counts: dict[str, int] = {}
        load_counts:     dict[str, int] = {}

        for rec in records:
            if start and rec.entry_time < start:
                continue
            if end and rec.entry_time > end:
                continue
            target = location_counts if rec.record_type == 'location' else load_counts
            target[rec.location_id] = target.get(rec.location_id, 0) + 1

        return {'location': location_counts, 'load': load_counts}

    # ── helpers ───────────────────────────────────────────────────────────────

    def _find_container_location(self, container_id: str) -> Optional[str]:
        for loc_id, loc in self._storage.get_locs().items():
            if any(str(c) == container_id for c in loc.ContainerIds):
                return str(loc_id)
        return None
