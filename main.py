# from api.old.app import start_api
# from api.capi import app_factory
# from api.routers.channel_router import
from coopstorage.storage2.loc_load.main import app
import uvicorn

if __name__ == "__main__":
    # start_api(port=5001)
    uvicorn.run(app, port=1219)