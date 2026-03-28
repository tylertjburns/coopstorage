import logging
from fastapi import APIRouter, Response
from pydantic import BaseModel
from typing import Dict, Tuple, Iterable
from coopstorage.storage2.loc_load.storage import Storage
from coopstorage.storage2.loc_load import dcs
from coopstorage.storage2.loc_load.qualifiers import LocationQualifier

logger = logging.getLogger(__name__)

class ApiLoads(BaseModel):
    loads: Iterable[dcs.Load]

class APIUnitOfMeasure(BaseModel):
    name: str
    each_qty: int = 1
    dimensions: Tuple[float,float,float] = None


def load_router_factory(
    storage: Storage
):
    load_router = APIRouter()

    # @load_router.put("/uoms")
    # def put_uom(uom: APIUnitOfMeasure):
    #     print("UOM Put")
    #     UOMS[uom.name] = uom
    #     return UOMS[uom.name]
    #
    # @load_router.get("/uoms/{uom}")
    # def get_uom(uom: str):
    #     return {"uom_name": uom,
    #             "details": UOMS[uom]}
    #
    # @load_router.get("/uoms")
    # def get_uoms():
    #     return UOMS

    @load_router.put("/loads")
    def put_load(loads: ApiLoads):
        # if load.uom not in UOMS.keys():
        #     return Response(status_code=424,
        #                     content={"error": f"UoM \'{load.uom}\' was provided, but was not found in UoM data store"})

        ret = storage.register_loads(
            loads=loads.loads
        ).get_loads(criteria=qs.g)
        return storage.

    @load_router.get("/loads")
    def get_loads() -> Dict[str, ApiLoad]:
        return LOADS

    @load_router.get("/loads/{lpn}")
    def get_load(lpn: str):
        return LOADS[lpn]

    return load_router