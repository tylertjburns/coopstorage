import asyncio
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pubsub import pub
from coopstorage.enums import StorageTopic


@dataclass
class StorageEvent:
    type: str
    payload: Dict[str, Any]


@dataclass
class _SubscriberState:
    id: str
    buffer: deque = field(default_factory=deque)
    last_seen: float = field(default_factory=time.time)
    evicted: bool = False
    _queue: Optional[asyncio.Queue] = field(default=None, repr=False)
    _loop: Optional[asyncio.AbstractEventLoop] = field(default=None, repr=False)


class StorageEventBus:
    """
    Bridges internal pypubsub events to external SSE subscribers.

    Subscribers have an explicit lifecycle:
      POST /subscribe   → subscribe()       → subscriber_id
      GET  /events/{id} → connect_sse()     → asyncio.Queue (live push)
      disconnect        → disconnect_sse()  → buffer accumulates
      POST /unsubscribe → unsubscribe()     → cleanup

    Buffer overflow (cap reached while disconnected) evicts the subscriber.
    Disconnected subscribers with no activity are cleaned up after ttl_seconds.
    """

    def __init__(self, ttl_seconds: float = 90.0, buffer_cap: int = 1000):
        self._ttl = ttl_seconds
        self._buffer_cap = buffer_cap
        self._lock = threading.Lock()
        self._subscribers: Dict[str, _SubscriberState] = {}

        pub.subscribe(self._on_location_registered,   StorageTopic.LOCATION_REGISTERED.value)
        pub.subscribe(self._on_container_registered,  StorageTopic.CONTAINER_REGISTERED.value)
        pub.subscribe(self._on_container_moved,       StorageTopic.CONTAINER_MOVED.value)
        pub.subscribe(self._on_content_changed,       StorageTopic.CONTENT_CHANGED.value)
        pub.subscribe(self._on_container_removed,     StorageTopic.CONTAINER_REMOVED.value)
        pub.subscribe(self._on_container_reserved,    StorageTopic.CONTAINER_RESERVED.value)
        pub.subscribe(self._on_container_unreserved,  StorageTopic.CONTAINER_UNRESERVED.value)
        pub.subscribe(self._on_location_reserved,     StorageTopic.LOCATION_RESERVED.value)
        pub.subscribe(self._on_location_unreserved,   StorageTopic.LOCATION_UNRESERVED.value)
        pub.subscribe(self._on_reservation_failed,    StorageTopic.RESERVATION_FAILED.value)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def subscribe(self) -> str:
        sub_id = str(uuid.uuid4())
        with self._lock:
            self._subscribers[sub_id] = _SubscriberState(id=sub_id)
        return sub_id

    def unsubscribe(self, sub_id: str):
        with self._lock:
            self._subscribers.pop(sub_id, None)

    def connect_sse(self, sub_id: str, loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
        """
        Attach a live asyncio.Queue to an existing subscriber.
        Buffered events are drained into the queue before returning so the
        client receives any events that arrived while disconnected.
        Raises KeyError if the subscriber is unknown or has been evicted.
        """
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            state = self._subscribers.get(sub_id)
            if state is None or state.evicted:
                raise KeyError(sub_id)
            while state.buffer:
                loop.call_soon_threadsafe(q.put_nowait, state.buffer.popleft())
            state._queue = q
            state._loop = loop
            state.last_seen = time.time()
        return q

    def disconnect_sse(self, sub_id: str):
        """Detach the live queue; buffer continues to accumulate events."""
        with self._lock:
            state = self._subscribers.get(sub_id)
            if state:
                state._queue = None
                state._loop = None
                state.last_seen = time.time()

    def cleanup_expired(self):
        """Remove disconnected subscribers whose TTL has elapsed."""
        cutoff = time.time() - self._ttl
        with self._lock:
            expired = [
                sid for sid, s in self._subscribers.items()
                if s._queue is None and s.last_seen < cutoff
            ]
            for sid in expired:
                del self._subscribers[sid]

    # ── internal emit ─────────────────────────────────────────────────────────

    def _emit(self, event: StorageEvent):
        with self._lock:
            evict: List[str] = []
            for sid, state in self._subscribers.items():
                if state.evicted:
                    evict.append(sid)
                    continue
                if state._queue is not None and state._loop is not None:
                    state._loop.call_soon_threadsafe(state._queue.put_nowait, event)
                    state.last_seen = time.time()
                else:
                    if len(state.buffer) >= self._buffer_cap:
                        state.evicted = True
                        evict.append(sid)
                    else:
                        state.buffer.append(event)
            for sid in evict:
                del self._subscribers[sid]

    # ── pypubsub handlers ─────────────────────────────────────────────────────

    def _on_location_registered(self, payload):
        self._emit(StorageEvent('location_registered', payload))

    def _on_container_registered(self, payload):
        self._emit(StorageEvent('container_registered', payload))

    def _on_container_moved(self, payload):
        self._emit(StorageEvent('container_moved', payload))

    def _on_content_changed(self, payload):
        self._emit(StorageEvent('content_changed', payload))

    def _on_container_removed(self, payload):
        self._emit(StorageEvent('container_removed', payload))

    def _on_container_reserved(self, payload):
        self._emit(StorageEvent('container_reserved', payload))

    def _on_container_unreserved(self, payload):
        self._emit(StorageEvent('container_unreserved', payload))

    def _on_location_reserved(self, payload):
        self._emit(StorageEvent('location_reserved', payload))

    def _on_location_unreserved(self, payload):
        self._emit(StorageEvent('location_unreserved', payload))

    def _on_reservation_failed(self, payload):
        self._emit(StorageEvent('reservation_failed', payload))
