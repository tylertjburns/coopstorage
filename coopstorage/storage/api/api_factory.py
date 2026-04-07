import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI
from fastapi.routing import APIRouter
from fastapi.staticfiles import StaticFiles

from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.data.storageDataStore import StorageDataStore
from coopstorage.storage.loc_load.event_bus import StorageEventBus
from coopstorage.storage.api.routers import v1

logger = logging.getLogger(__name__)


def _v1_router(storage: Storage, event_bus: StorageEventBus) -> APIRouter:
    router = APIRouter(prefix="/v1")
    router.include_router(v1.container_router_factory(storage),          tags=["containers"])
    router.include_router(v1.location_router_factory(storage),           tags=["locations"])
    router.include_router(v1.transfer_request_router_factory(storage),   tags=["transfer_requests"])
    router.include_router(v1.snapshot_router_factory(storage),           tags=["snapshot"])
    router.include_router(v1.events_router_factory(event_bus),           tags=["events"])
    router.include_router(v1.tree_router_factory(storage))
    router.include_router(v1.generate_router_factory(storage))
    router.include_router(v1.simulate_router_factory(storage, event_bus))
    return router


def storage_api_factory(
    storage: Optional[Storage] = None,
    version_routers: Optional[List[APIRouter]] = None,
) -> FastAPI:
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

    for router in (version_routers or [_v1_router(storage, event_bus)]):
        app.include_router(router)

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
