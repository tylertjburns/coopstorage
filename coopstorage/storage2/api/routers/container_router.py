import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Tuple, Iterable, Optional
from coopstorage.storage2.loc_load.storage import Storage
from coopstorage.storage2.loc_load import dcs

logger = logging.getLogger(__name__)


class ApiContainer(BaseModel):
    id: str
    uom: Optional[str] = None
    weight: Optional[float] = None


class ApiContainers(BaseModel):
    containers: List[ApiContainer]


def container_router_factory(storage: Storage):
    container_router = APIRouter()

    @container_router.put("/containers")
    def put_container(body: ApiContainers):
        containers = [dcs.Container(id=c.id) for c in body.containers]
        storage.register_containers(containers=containers)
        return {str(k): str(v) for k, v in storage.get_containers().items()}

    @container_router.get("/containers")
    def get_containers() -> Dict[str, str]:
        return {str(k): str(v) for k, v in storage.get_containers().items()}

    @container_router.get("/containers/{container_id}")
    def get_container(container_id: str):
        containers = storage.get_containers()
        if container_id not in containers:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Container '{container_id}' not found")
        return containers[container_id]

    return container_router
