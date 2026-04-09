from typing import Union, Tuple, Iterable, List
from fastapi import FastAPI, Response
from pydantic import BaseModel
from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria
from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.location import Location
from cooptools.common import LETTERS
import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.channel_processors as cps
import logging
from coopstorage.storage.loc_load.data.storageDataStore import StorageDataStore
from pprint import pprint
from coopstorage.storage.loc_load import qualifiers as qs

logger = logging.getLogger(__name__)
app = FastAPI()

storage = Storage(
    data_store=StorageDataStore()
)


class UnitOfMeasure(BaseModel):
    each_qty: int = 1
    dimensions: Tuple[float,float,float] = None

class Load(BaseModel):
    uom: str

class TransferRequestAPIWrapper(BaseModel):
    requests: Iterable[TransferRequestCriteria]

class CoordAPI(BaseModel):
    x: float
    y: float
    z: float

    def as_tuple(self):
        return (self.x, self.y, self.z)

class LocationMetaAPI(BaseModel):
    dims: CoordAPI
    channel_processor_type: str
    capacity: int

    def as_loc_meta(self) -> dcs.LocationMeta:
        return dcs.LocationMeta(
                dims=self.dims.as_tuple(),
                channel_processor=cps.ChannelProcessorType.by_str(self.channel_processor_type),
                capacity=self.capacity
            )

class LocationAPI(BaseModel):
    id: str
    meta: LocationMetaAPI
    coords: CoordAPI

    def as_loc(self) -> Location:
        return Location(
            id=self.id,
            location_meta=self.meta.as_loc_meta(),
            coords=self.coords.as_tuple()
        )

class LocationsRequestAPIWrapper(BaseModel):
    locations: Iterable[LocationAPI]

UOMS = {}
LOADS = {}


@app.put('/transferRequests')
def put_transfer_request(
        transfer_request_criteria: TransferRequestAPIWrapper
):
    requests_str = '\n\t'.join(str(x) for x in transfer_request_criteria.requests)
    logger.info(f"Received Transfer Requests: \n{requests_str}")

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


@app.get("/locations")
def get_locations():
    return storage.Locations

@app.put("/locations")
def put_locations(location_request: LocationsRequestAPIWrapper):
    locs = [x.as_loc() for x in location_request.locations]
    pprint(locs)
    storage.register_locs(
        locs=locs
    ).get_locs(criteria=qs.LocationQualifier())

    msg = f"Locations {','.join(x.as_loc().get_id() for x in location_request.locations)} added successfully"
    logger.info(msg)
    return Response(
        content=msg,
        status_code=200
    )
@app.put("/locations/eg")
def put_eg_locations():
    return put_locations(
        LocationsRequestAPIWrapper(
            locations=[
                LocationAPI(id=LETTERS[ii],
                            meta=LocationMetaAPI(
                                dims=CoordAPI(x=10, y=10, z=10),
                                channel_processor_type=cps.ChannelProcessorType.FIFOFlowChannelProcessor.name,
                                capacity=3
                            ),
                            coords=CoordAPI(x=100, y=200, z=300)
                            ) for ii in range(10)]
        )
    )




if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.DEBUG)
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