import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Tuple, Iterable, Optional
from coopstorage.storage2.loc_load.storage import Storage
from coopstorage.storage2.loc_load import dcs

logger = logging.getLogger(__name__)


class ApiLoad(BaseModel):
    id: str
    uom: Optional[str] = None
    weight: Optional[float] = None


class ApiLoads(BaseModel):
    loads: List[ApiLoad]


def load_router_factory(storage: Storage):
    load_router = APIRouter()

    @load_router.put("/loads")
    def put_load(body: ApiLoads):
        loads = [dcs.Load(id=l.id) for l in body.loads]
        storage.register_loads(loads=loads)
        return {str(k): str(v) for k, v in storage.get_loads().items()}

    @load_router.get("/loads")
    def get_loads() -> Dict[str, str]:
        return {str(k): str(v) for k, v in storage.get_loads().items()}

    @load_router.get("/loads/{load_id}")
    def get_load(load_id: str):
        loads = storage.get_loads()
        if load_id not in loads:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Load '{load_id}' not found")
        return loads[load_id]

    return load_router