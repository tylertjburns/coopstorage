import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from coopstorage.storage.loc_load.event_bus import StorageEventBus

logger = logging.getLogger(__name__)

_SSE_KEEPALIVE_SECONDS = 15.0


def events_router_factory(event_bus: StorageEventBus) -> APIRouter:
    router = APIRouter()

    @router.post("/subscribe")
    def post_subscribe() -> dict:
        """Register a new subscriber. Returns a subscriber_id for use with /events and /unsubscribe."""
        return {"subscriber_id": event_bus.subscribe()}

    @router.get("/events/{subscriber_id}")
    async def get_events(subscriber_id: str):
        """
        Open an SSE stream for the given subscriber_id.
        Events are pushed immediately as they occur; a keep-alive ping is sent
        every 15 s of silence. Buffered events from while disconnected are
        delivered first, then live events follow.
        Returns 404 if the subscriber_id is unknown or was evicted due to buffer overflow.
        """
        loop = asyncio.get_running_loop()
        try:
            q = event_bus.connect_sse(subscriber_id, loop)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail="Subscriber not found or evicted — call POST /subscribe to obtain a new id",
            )

        async def stream():
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(q.get(), timeout=_SSE_KEEPALIVE_SECONDS)
                        data = json.dumps({'type': event.type, 'payload': event.payload})
                        yield f"data: {data}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                event_bus.disconnect_sse(subscriber_id)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/unsubscribe/{subscriber_id}")
    def post_unsubscribe(subscriber_id: str) -> dict:
        """Explicitly remove a subscriber and release its buffer."""
        event_bus.unsubscribe(subscriber_id)
        return {"unsubscribed": subscriber_id}

    return router
