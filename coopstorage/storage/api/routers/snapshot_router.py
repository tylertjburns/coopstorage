import logging
from typing import Dict, List, Optional

from fastapi import APIRouter

from coopstorage.storage.loc_load.location import Location
from coopstorage.storage.loc_load.storage import Storage

logger = logging.getLogger(__name__)


def _serialize_location(loc: Location, all_containers: dict) -> dict:
    positions = loc.ContainerPositions  # {slot_idx: container_id | None}
    slots: List[Optional[str]] = [
        str(positions[i]) if positions.get(i) is not None else None
        for i in range(loc.Capacity)
    ]

    loc_containers: Dict[str, dict] = {}
    for cid in loc.ContainerIds:
        if cid in all_containers:
            c = all_containers[cid]
            loc_containers[str(cid)] = {
                'id': str(c.id),
                'uom': c.uom.name,
                'contents': [
                    {'resource': cc.resource.name, 'uom': cc.uom.name, 'qty': cc.qty}
                    for cc in c.contents
                ]
            }

    cp = loc.Meta.channel_processor
    state = [positions.get(i) for i in range(loc.Capacity)]
    try:
        addable_slots = cp.get_addable_positions(state)
    except StopIteration:
        addable_slots = []
    try:
        removable_slots = cp.get_removable_positions(state)
    except StopIteration:
        removable_slots = []

    return {
        'id': str(loc.Id),
        'coords': list(loc.Coords),
        'meta': {
            'dims': list(loc.Meta.dims),
            'channel_processor': type(loc.Meta.channel_processor).__name__,
            'capacity': loc.Capacity,
            'channel_axis': loc.Meta.channel_axis,
            'delete_on_receive': loc.Meta.delete_on_receive,
        },
        'slot_dims':    list(loc.SlotDims),
        'slot_offsets': [list(o) for o in loc.SlotOffsets],
        'slots': slots,
        'addable_slots':  addable_slots,
        'removable_slots': removable_slots,
        'containers': loc_containers,
    }


def snapshot_router_factory(storage: Storage) -> APIRouter:
    router = APIRouter()

    @router.get("/snapshot")
    def get_snapshot(offset: int = 0, limit: int = 1000) -> dict:
        locs = storage.get_locs()
        containers = storage.get_containers()
        all_ids = list(locs.keys())
        total = len(all_ids)
        page_ids = all_ids[offset:offset + limit]
        return {
            'total': total,
            'offset': offset,
            'locations': {
                str(loc_id): _serialize_location(locs[loc_id], containers)
                for loc_id in page_ids
            }
        }

    return router
