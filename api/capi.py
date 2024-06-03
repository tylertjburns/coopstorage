from fastapi import FastAPI
from coopstorage.storage import Storage
from api.routers.location_router import location_router_factory
from api.routers.channel_router import channel_router_factory, Channels

def app_factory():

    app = FastAPI()


    # storage = Storage(locations=[])
    # location_router = location_router_factory(storage=storage)
    # app.include_router(location_router.router, tags=["triggers"])
    #
    channel_router = channel_router_factory(channels=Channels())
    app.include_router(channel_router, tags=["triggers"])

    return app