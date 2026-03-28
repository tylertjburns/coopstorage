import logging
from fastapi import FastAPI

from coopstorage.storage2.loc_load.storage import Storage
from coopstorage.storage2.loc_load.data.storageDataStore import StorageDataStore
from coopstorage.storage2.api.routers.load_router import load_router_factory
from coopstorage.storage2.api.routers.location_router import location_router_factory
from coopstorage.storage2.api.routers.transfer_request_router import transfer_request_router_factory

logger = logging.getLogger(__name__)


def storage_api_factory(storage: Storage = None) -> FastAPI:
    if storage is None:
        storage = Storage(data_store=StorageDataStore())

    app = FastAPI()

    app.include_router(load_router_factory(storage), tags=["loads"])
    app.include_router(location_router_factory(storage), tags=["locations"])
    app.include_router(transfer_request_router_factory(storage), tags=["transfer_requests"])

    @app.get("/")
    def health_check():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    import uvicorn

    app = storage_api_factory()
    uvicorn.run(app, host="localhost", port=1219, log_level="info")
