import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from coopstorage.storage.loc_load.location import Location
from coopstorage.storage.loc_load import dcs
import coopstorage.storage.loc_load.channel_processors as cps
from coopstorage.storage.layout_manager import LayoutManager
from coopstorage.storage.loc_load.data.sql.sql_layout_data_store import LayoutRecord
from coopstorage.storage.loc_load.data.sql.sql_location_data_store import SqlLocationDataStore
from coopstorage.storage.api.routers.v1.location_router import (
    CoordAPI,
    LocationMetaAPI,
    LocationAPI,
    LocationsRequestAPIWrapper,
)
from coopstorage.storage.api.routers.v1.snapshot_router import _serialize_location

logger = logging.getLogger(__name__)


# ── Request/response models ────────────────────────────────────────────────────

class CreateLayoutRequest(BaseModel):
    name: str
    description: Optional[str] = None


class PatchLayoutRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class PatchLocationRequest(BaseModel):
    coords: Optional[CoordAPI] = None
    meta: Optional[LocationMetaAPI] = None
    tree_labels: Optional[Dict[str, Any]] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_layout(manager: LayoutManager, layout_id: str) -> LayoutRecord:
    record = manager.get_layout(layout_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Layout '{layout_id}' not found")
    return record


def _get_sql_loc_store(storage) -> Optional[SqlLocationDataStore]:
    """Unwrap the SqlLocationDataStore from Storage, or None for non-SQL backends."""
    underlying = storage._data_store.LocationsData._data_store
    return underlying if isinstance(underlying, SqlLocationDataStore) else None


# ── Router factory ─────────────────────────────────────────────────────────────

def layout_router_factory(layout_manager: LayoutManager) -> APIRouter:
    router = APIRouter()

    # ── Layouts ────────────────────────────────────────────────────────────────

    @router.get("/layouts", response_model=List[LayoutRecord])
    def list_layouts():
        return layout_manager.list_layouts()

    @router.post("/layouts", response_model=LayoutRecord, status_code=201)
    def create_layout(body: CreateLayoutRequest):
        return layout_manager.create_layout(body.name, body.description)

    @router.get("/layouts/{layout_id}", response_model=LayoutRecord)
    def get_layout(layout_id: str):
        return _require_layout(layout_manager, layout_id)

    @router.patch("/layouts/{layout_id}", response_model=LayoutRecord)
    def patch_layout(layout_id: str, body: PatchLayoutRequest):
        _require_layout(layout_manager, layout_id)
        updated = layout_manager.update_layout(layout_id, body.name, body.description)
        if updated is None:
            raise HTTPException(status_code=404, detail=f"Layout '{layout_id}' not found")
        return updated

    @router.delete("/layouts/{layout_id}", status_code=204)
    def delete_layout(layout_id: str):
        _require_layout(layout_manager, layout_id)
        layout_manager.delete_layout(layout_id)

    # ── Locations ──────────────────────────────────────────────────────────────

    @router.get("/layouts/{layout_id}/locations")
    def list_locations(layout_id: str) -> Dict[str, dict]:
        _require_layout(layout_manager, layout_id)
        storage = layout_manager.get_storage(layout_id)
        locs = storage.get_locs()
        containers = storage.get_containers()
        tree = storage.LocationMapTree
        result = {}
        for loc_id, loc in locs.items():
            entry = _serialize_location(loc, containers)
            try:
                entry['tree_path'] = tree.get_path(loc_id)
            except KeyError:
                entry['tree_path'] = None
            result[str(loc_id)] = entry
        return result

    @router.put("/layouts/{layout_id}/locations")
    def put_locations(layout_id: str, body: LocationsRequestAPIWrapper):
        _require_layout(layout_manager, layout_id)
        storage = layout_manager.get_storage(layout_id)
        pg_store = _get_sql_loc_store(storage)

        # Register tree labels in the LocationMapTree first so SSE events
        # include tree_path from the initial LOCATION_REGISTERED event.
        for loc_api in body.locations:
            if loc_api.tree_labels:
                storage.LocationMapTree.register(loc_api.id, **loc_api.tree_labels)

        locs = [x.as_loc() for x in body.locations]
        try:
            storage.register_locs(locs=locs)
        except IntegrityError:
            existing = [x.id for x in body.locations if x.id in storage.get_locs()]
            dup_label = ', '.join(existing) if existing else 'one or more locations'
            raise HTTPException(
                status_code=409,
                detail=f"Location(s) already exist in this layout: {dup_label}. Choose a different Zone name.",
            )

        # Persist tree labels to the locations row in Postgres.
        if pg_store is not None:
            for loc_api in body.locations:
                if loc_api.tree_labels:
                    pg_store.upsert_tree_labels(loc_api.id, loc_api.tree_labels)

        return {"registered": [x.id for x in body.locations]}

    @router.get("/layouts/{layout_id}/locations/{loc_id}")
    def get_location(layout_id: str, loc_id: str):
        _require_layout(layout_manager, layout_id)
        storage = layout_manager.get_storage(layout_id)
        locs = storage.get_locs()
        if loc_id not in locs:
            raise HTTPException(
                status_code=404,
                detail=f"Location '{loc_id}' not found in layout '{layout_id}'",
            )
        return Location.to_jsonable_dict(locs[loc_id])

    @router.patch("/layouts/{layout_id}/locations/{loc_id}")
    def patch_location(layout_id: str, loc_id: str, body: PatchLocationRequest):
        _require_layout(layout_manager, layout_id)
        storage = layout_manager.get_storage(layout_id)
        locs = storage.get_locs()
        if loc_id not in locs:
            raise HTTPException(
                status_code=404,
                detail=f"Location '{loc_id}' not found in layout '{layout_id}'",
            )
        existing = locs[loc_id]
        new_coords = body.coords.as_tuple() if body.coords else existing.Coords
        new_meta = body.meta.as_loc_meta() if body.meta else existing.Meta

        updated = Location(
            id=loc_id,
            location_meta=new_meta,
            coords=new_coords,
            channel_state=existing.ContainerPositions or None,
        )
        storage._data_store.LocationsData.update([updated])

        pg_store = _get_sql_loc_store(storage)
        if body.tree_labels and pg_store is not None:
            storage.LocationMapTree.register(loc_id, **body.tree_labels)
            pg_store.upsert_tree_labels(loc_id, body.tree_labels)

        return Location.to_jsonable_dict(updated)

    @router.delete("/layouts/{layout_id}/locations/{loc_id}", status_code=204)
    def delete_location(layout_id: str, loc_id: str):
        _require_layout(layout_manager, layout_id)
        storage = layout_manager.get_storage(layout_id)
        locs = storage.get_locs()
        if loc_id not in locs:
            raise HTTPException(
                status_code=404,
                detail=f"Location '{loc_id}' not found in layout '{layout_id}'",
            )
        storage._data_store.LocationsData.remove(ids=[loc_id])

    @router.delete("/layouts/{layout_id}/locations", status_code=204)
    def clear_locations(layout_id: str):
        _require_layout(layout_manager, layout_id)
        storage = layout_manager.get_storage(layout_id)
        storage._data_store.LocationsData.clear()

    return router
