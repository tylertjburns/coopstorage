import logging
import uuid

import coopstorage.storage.loc_load.dcs as dcs
from cooptools.protocols import UniqueIdentifier
from typing import List, Optional, Dict, Iterable, Self
from cooptools.geometry_utils import vector_utils as vec
from coopstorage.storage.loc_load.channel import Channel

logger = logging.getLogger(__name__)

class Location:
    def __init__(self,
                 id: UniqueIdentifier,
                 location_meta: dcs.LocationMeta,
                 coords: vec.FloatVec,
                 channel_state: Dict[int, UniqueIdentifier] = None):
        self._id = id
        self._coords: vec.FloatVec = coords
        self._meta = location_meta
        self._channel: Channel = Channel(
            processor=location_meta.channel_processor,
            id=f"{id}_channel",
            capacity=location_meta.capacity,
            init_state=channel_state
        )
        self._reservation_token = None
        self._validate_geometry()

    def _validate_geometry(self):
        dims = self._meta.dims
        axis = self._meta.channel_axis
        if axis >= len(dims):
            raise ValueError(
                f"Location '{self._id}': channel_axis={axis} is out of range for dims {dims}"
            )
        if any(d <= 0 for d in dims):
            raise ValueError(
                f"Location '{self._id}': all dims must be > 0, got {dims}"
            )

    @property
    def SlotDims(self) -> vec.FloatVec:
        """3D size of each slot (location dims divided along channel_axis by capacity)."""
        dims = list(self._meta.dims)
        dims[self._meta.channel_axis] = dims[self._meta.channel_axis] / self.Capacity
        return tuple(dims)

    @property
    def SlotOffsets(self) -> List[vec.FloatVec]:
        """Per-slot offset from loc.Coords to that slot's origin corner."""
        axis   = self._meta.channel_axis
        step   = self.SlotDims[axis]
        result = []
        for i in range(self.Capacity):
            off = [0.0] * len(self._meta.dims)
            off[axis] = i * step
            result.append(tuple(off))
        return result

    @property
    def Capacity(self) -> int:
        return self._meta.capacity

    @property
    def AvailableCapacity(self) -> int:
        return self._meta.capacity - len(self.ContainerIds)

    @property
    def ContainerPositions(self) -> Dict[int, UniqueIdentifier]:
        return {ii: x for ii, x in enumerate(self._channel.State)}

    @property
    def Id(self) -> UniqueIdentifier:
        return self._id

    @property
    def Meta(self) -> dcs.LocationMeta:
        return self._meta

    @property
    def Coords(self) -> vec.FloatVec:
        return self._coords

    @property
    def ContainerIds(self) -> List[UniqueIdentifier]:
        return self._channel.StoredIds

    @property
    def Slots(self) -> list:
        pos = self.ContainerPositions
        return [str(pos[i]) if pos.get(i) is not None else None for i in range(self.Capacity)]

    def channel_access_state(self) -> dict:
        return {
            'addable_slots':  self.get_addable_positions(),
            'removable_slots': self.get_removable_positions(),
        }

    def get_removable_positions(self):
        return self._channel.get_removable_positions()

    def get_addable_positions(self):
        return self._channel.get_addable_positions()

    def get_removable_container_ids(self) -> Dict[int, UniqueIdentifier]:
        """Returns {channel_position: container_id} for all currently removable positions."""
        return self._channel.get_removable_ids()

    def store_containers(self, container_ids: Iterable[UniqueIdentifier]):
        logger.info(f"Storing containers {[x for x in container_ids]} in location \'{self._id}\': {str(self._channel)}")
        self._channel.store(container_ids)
        logger.info(f"Done storing containers {[x for x in container_ids]} in location \'{self._id}\': {str(self._channel)}")
        return self

    def remove_containers(self, container_ids: Iterable[UniqueIdentifier]):
        logger.info(f"Removing containers {[x for x in container_ids]} from location \'{self._id}\': {str(self._channel)}")
        self._channel.remove(container_ids)
        logger.info(f"Done removing containers {[x for x in container_ids]} from location \'{self._id}\': {str(self._channel)}")
        return self

    def clear_containers(self):
        self._channel.clear()

    def set_reservation_token(self, token: uuid.UUID):
        self._reservation_token = token

    def remove_reservation_token(self, token: uuid.UUID):
        if self._reservation_token == token:
            self._reservation_token = None

    @property
    def Reserved(self) -> bool:
        return self._reservation_token is not None

    def verify_removable(self, container_id: UniqueIdentifier):
        return self._meta.channel_processor.verify_removable(container_id, state=self._channel.State)

    def summary(self) -> Dict[UniqueIdentifier, List[UniqueIdentifier]]:
        return {k.Id: [ld.id for ld in v] for k, v in self.LocLoads.items()}

    def __repr__(self):
        return f"{self._id}: {self.ContainerPositions}"

    def get_id(self) -> UniqueIdentifier:
        return self._id

    @classmethod
    def to_jsonable_dict(cls, obj: Self) -> Dict:
        return {
            'id': str(obj._id),
            'meta': obj._meta.to_jsonable_dict(),
            'channel': {str(k): v for k, v in obj._channel.PopulatedIdxs.items()},
            'coords': obj._coords
        }

    @classmethod
    def from_jsonable_dict(cls, data: Dict) -> Self:
        return Location(
            id=data['id'],
            location_meta=dcs.LocationMeta(**data['meta']),
            coords=data['coords'],
            channel_state={int(k): v for k, v in data['channel'].items()}
        )


if __name__ == "__main__":
    import coopstorage.storage.loc_load.channel_processors as cps
    logging.basicConfig(level=logging.DEBUG)
    l_a = Location(
        id='a',
        location_meta=dcs.LocationMeta(
            channel_processor=cps.LIFOFlowBackwardChannelProcessor(),
            capacity=2,
            dims=(100, 100, 100),
        ),
        coords=(1, 1, 1)
    )

    lpn1 = dcs.Load(
        id='1',
        uom=dcs.UnitOfMeasure(name="ea"),
    )
    lpn2 = dcs.Load(
        id='2',
        uom=dcs.UnitOfMeasure(name="ea"),
    )
    l_a.store_containers([lpn1.id])
    l_a.store_containers([lpn2.id])
    l_a.remove_containers([lpn2.id])
