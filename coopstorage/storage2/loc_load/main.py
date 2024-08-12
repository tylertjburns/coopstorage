from typing import Union, Tuple, Iterable
from fastapi import FastAPI, Response
from pydantic import BaseModel
from coopstorage.storage2.loc_load.transferRequest import TransferRequestCriteria
from coopstorage.storage2.loc_load.storage import Storage
from coopstorage.storage2.loc_load.location import Location
from cooptools.common import LETTERS
import coopstorage.storage2.loc_load.dcs as dcs
import coopstorage.storage2.loc_load.channel_processors as cps
import logging

logger = logging.getLogger(__name__)
app = FastAPI()

storage = Storage(
    locs=[
        Location(id=LETTERS[ii],
                 location_meta=dcs.LocationMeta(
                     dims=(10, 10, 10),
                     channel_processor=cps.FIFOFlowChannelProcessor(),
                     capacity=3
                 ),
                 coords=(100, 200, 300)
                 ) for ii in range(10)],
)


class UnitOfMeasure(BaseModel):
    each_qty: int = 1
    dimensions: Tuple[float,float,float] = None

class Load(BaseModel):
    uom: str

class TransferRequestAPIWrapper(BaseModel):
    requests: Iterable[TransferRequestCriteria]

UOMS = {}
LOADS = {}


@app.put('/transferRequests')
def put_transfer_request(
        transfer_request_criteria: TransferRequestAPIWrapper
):
    logger.info("Received Transfer Requests: "
                f"\n{'\n\t'.join(str(x) for x in transfer_request_criteria.requests)}")

    storage.handle_transfer_requests(
        transfer_request_criteria=transfer_request_criteria.requests
    )

    return Response(
        content=str(transfer_request_criteria),
        status_code=200
    )

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/uoms/{uom}")
def get_uom(uom: str):
    return {"uom_name": uom,
            "details": UOMS[uom]}

@app.get("/uoms")
def get_uoms():
    return UOMS

@app.put("/uoms/{uom_name}")
def put_uom(uom_name: str, uom: UnitOfMeasure):
    print("UOM Put")
    UOMS[uom_name] = uom
    return {"uom_name": uom_name, "details": uom}

@app.get("/loads/{lpn}")
def get_load(lpn: str,):
    return {"lpn": lpn,
            "details": LOADS[lpn]}

@app.get("/loads")
def get_loads():
    return LOADS

@app.put("/loads/{lpn}")
def put_load(lpn: str, load: Load):
    LOADS[lpn] = load
    return LOADS[lpn]

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    # put_uom("123", UnitOfMeasure(each_qty=1, dimensions=(10, 10, 10)))
    # put_uom("234", UnitOfMeasure(each_qty=1, dimensions=(20, 10, 10)))
    # put_uom("345", UnitOfMeasure(each_qty=1, dimensions=(30, 10, 10)))
    # put_load("A1", Load(uom=123))

    uvicorn.run(
        "main:app",
        port=5000,
        log_level="info",
        reload=True
    )