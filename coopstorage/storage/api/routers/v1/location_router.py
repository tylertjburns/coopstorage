import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Iterable, List, Tuple, Dict, Any

from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load import dcs
from coopstorage.storage.loc_load import qualifiers as qs
import coopstorage.storage.loc_load.channel_processors as cps
from coopstorage.storage.loc_load.location import Location
from cooptools.common import LETTERS

logger = logging.getLogger(__name__)


class CoordAPI(BaseModel):
    x: float
    y: float
    z: float

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


class LocationMetaAPI(BaseModel):
    dims: CoordAPI
    channel_processor_type: str
    capacity: int = 1

    def as_loc_meta(self) -> dcs.LocationMeta:
        return dcs.LocationMeta(
            dims=self.dims.as_tuple(),
            channel_processor=cps.ChannelProcessorType.by_str(self.channel_processor_type).value,
            capacity=self.capacity,
        )


class LocationAPI(BaseModel):
    id: str
    meta: LocationMetaAPI
    coords: CoordAPI
    tree_labels: Dict[str, Any] = {}

    def as_loc(self) -> Location:
        return Location(
            id=self.id,
            location_meta=self.meta.as_loc_meta(),
            coords=self.coords.as_tuple(),
        )


class LocationsRequestAPIWrapper(BaseModel):
    locations: List[LocationAPI]


def location_router_factory(storage: Storage) -> APIRouter:
    location_router = APIRouter()

    @location_router.get("/locations")
    def get_locations() -> Dict[str, dict]:
        locs = storage.get_locs()
        return {str(k): Location.to_jsonable_dict(v) for k, v in locs.items()}

    @location_router.put("/locations")
    def put_locations(body: LocationsRequestAPIWrapper):
        # Register tree labels first so location_registered events include tree_path
        for loc_api in body.locations:
            if loc_api.tree_labels:
                storage.LocationMapTree.register(loc_api.id, **loc_api.tree_labels)
        locs = [x.as_loc() for x in body.locations]
        storage.register_locs(locs=locs)
        ids = [x.id for x in body.locations]
        logger.info(f"Locations registered: {ids}")
        return {"registered": ids}

    @location_router.delete("/locations/{location_id}")
    def delete_location(location_id: str):
        locs = storage.get_locs()
        if location_id not in locs:
            raise HTTPException(status_code=404, detail=f"Location '{location_id}' not found")
        # Re-register all locations except the deleted one
        remaining = [v for k, v in locs.items() if str(k) != location_id]
        storage._data_store.LocationsData.clear()
        storage.register_locs(locs=remaining)
        return {"deleted": location_id}

    @location_router.get("/locations/{location_id}")
    def get_location(location_id: str):
        locs = storage.get_locs()
        if location_id not in locs:
            raise HTTPException(status_code=404, detail=f"Location '{location_id}' not found")
        return Location.to_jsonable_dict(locs[location_id])

    @location_router.delete("/locations")
    def delete_all_locations():
        """Remove all locations and containers from storage."""
        return storage.clear_all()

    @location_router.put("/locations/eg")
    def put_eg_locations():
        """Register a set of 10 example FIFO locations (A–J)."""
        eg_locs = [
            Location(
                id=LETTERS[ii],
                location_meta=dcs.LocationMeta(
                    dims=(10, 10, 10),
                    channel_processor=cps.FIFOFlowChannelProcessor(),
                    capacity=3,
                ),
                coords=(100, 200, 300),
            )
            for ii in range(10)
        ]
        storage.register_locs(locs=eg_locs)
        return {"registered": [LETTERS[ii] for ii in range(10)]}

    return location_router
