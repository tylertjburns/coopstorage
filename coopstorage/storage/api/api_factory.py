import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.data.storageDataStore import StorageDataStore
from coopstorage.storage.loc_load.event_bus import StorageEventBus
from coopstorage.storage.api.routers.container_router import container_router_factory
from coopstorage.storage.api.routers.location_router import location_router_factory
from coopstorage.storage.api.routers.transfer_request_router import transfer_request_router_factory
from coopstorage.storage.api.routers.snapshot_router import snapshot_router_factory
from coopstorage.storage.api.routers.events_router import events_router_factory

logger = logging.getLogger(__name__)


def storage_api_factory(storage: Storage = None) -> FastAPI:
    event_bus = StorageEventBus()

    if storage is None:
        storage = Storage(data_store=StorageDataStore())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async def _ttl_cleanup():
            while True:
                await asyncio.sleep(30)
                event_bus.cleanup_expired()

        task = asyncio.create_task(_ttl_cleanup())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app = FastAPI(lifespan=lifespan)

    app.include_router(container_router_factory(storage),          tags=["containers"])
    app.include_router(location_router_factory(storage),           tags=["locations"])
    app.include_router(transfer_request_router_factory(storage),   tags=["transfer_requests"])
    app.include_router(snapshot_router_factory(storage),           tags=["snapshot"])
    app.include_router(events_router_factory(event_bus),           tags=["events"])

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def health_check():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    import uvicorn

    app = storage_api_factory()
    uvicorn.run(app, host="localhost", port=1219, log_level="info")
