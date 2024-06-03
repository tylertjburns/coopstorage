# from api.old.app import start_api
# from api.capi import app_factory
from api.routers.channel_router2 import app
import uvicorn

if __name__ == "__main__":
    # start_api(port=5001)
    uvicorn.run(app, host='0.0.0.0', port=1219)