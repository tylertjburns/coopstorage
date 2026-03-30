from coopstorage.storage.loc_load.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, port=1219)
