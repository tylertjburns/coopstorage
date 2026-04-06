import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria

logger = logging.getLogger(__name__)


class TransferRequestAPIWrapper(BaseModel):
    requests: List[TransferRequestCriteria]


def transfer_request_router_factory(storage: Storage) -> APIRouter:
    transfer_request_router = APIRouter()

    @transfer_request_router.put("/transferRequests")
    def put_transfer_requests(body: TransferRequestAPIWrapper):
        logger.info(
            f"Received {len(body.requests)} transfer request(s):\n"
            + "\n\t".join(str(r) for r in body.requests)
        )
        storage.handle_transfer_requests(transfer_request_criteria=body.requests)
        return {"processed": len(body.requests)}

    @transfer_request_router.get("/transferRequests")
    def get_transfer_requests():
        pending = storage._data_store.TransferRequestsData.get()
        return {str(k): v.to_jsonable_dict(v) for k, v in pending.items()}

    return transfer_request_router
