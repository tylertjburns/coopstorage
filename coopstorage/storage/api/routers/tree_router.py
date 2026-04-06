import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from coopstorage.storage.loc_load.storage import Storage

logger = logging.getLogger(__name__)


class LabelsBody(BaseModel):
    labels: Dict[str, Any] = {}


def tree_router_factory(storage: Storage) -> APIRouter:
    router = APIRouter(prefix="/tree", tags=["tree"])

    def _tree():
        return storage.LocationMapTree

    @router.get("/levels")
    def get_levels() -> List[str]:
        """Return all known hierarchy levels in registration order."""
        return _tree().levels

    @router.get("/level/{level_name}")
    def get_level(level_name: str) -> Dict[str, List[str]]:
        """Return all distinct nodes at a given level mapped to their loc_ids.

        Node keys are serialised as pipe-separated 'level=value' strings.
        """
        try:
            raw = _tree().get_all_at_level(level_name)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {
            "|".join(f"{lv}={val}" for lv, val in key): [str(lid) for lid in loc_ids]
            for key, loc_ids in raw.items()
        }

    @router.get("/locations/{loc_id}/path")
    def get_path(loc_id: str) -> Dict[str, Any]:
        """Return the full label dict for a registered location."""
        try:
            return _tree().get_path(loc_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.get("/locations/{loc_id}/siblings")
    def get_siblings(loc_id: str) -> List[str]:
        """Return all loc_ids that share the same parent labels."""
        try:
            return [str(lid) for lid in _tree().get_siblings(loc_id)]
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.post("/locations")
    def query_locations(body: LabelsBody) -> List[str]:
        """Return all loc_ids matching the supplied labels (partial match).

        Pass an empty labels dict to get every registered location.
        """
        return [str(lid) for lid in _tree().get_loc_ids(**body.labels)]

    @router.post("/children")
    def get_children(body: LabelsBody) -> List[Dict[str, Any]]:
        """Return distinct child-level label dicts one level below the supplied prefix."""
        return _tree().get_children(**body.labels)

    @router.post("/occupancy")
    def get_occupancy(body: LabelsBody) -> Dict[str, Any]:
        """Return rolled-up occupancy stats for the subtree matching labels."""
        return _tree().occupancy(storage, **body.labels)

    return router
