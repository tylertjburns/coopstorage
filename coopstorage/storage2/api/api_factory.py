from fastapi import APIRouter, FastAPI
from coopstorage.storage2.api.routers import load_router, location_router
def storage_api_factory() -> FastAPI:
    app = FastAPI()

    app.include_router(router=load_router)
    app.include_router(router=location_router)

    return app

if __name__ == "__main__":
    import uvicorn

    app = storage_api_factory()
    uvicorn.run(app,
                host='localhost',
                port=1219,
                log_level="info",
    )