import logging
import uuid

import coopstorage.storage2.loc_load.dcs as dcs
from cooptools.protocols import UniqueIdentifier
from typing import List, Optional, Dict, Iterable
from cooptools.geometry_utils import vector_utils as vec
from coopstorage.storage2.loc_load.channel import Channel
from cooptools.register import Register

logger = logging.getLogger(__name__)

class Location:
    def __init__(self,
                 id: UniqueIdentifier,
                 location_meta: dcs.LocationMeta,
                 coords: vec.FloatVec):
        self._id = id
        self._coords: vec.FloatVec = coords
        self._meta = location_meta
        self._channel: Channel = Channel(
            processor=location_meta.channel_processor,
            id=f"{id}_channel",
            capacity=location_meta.capacity
        )
        self._reservation_token = None

    @property
    def Capacity(self) -> int:
        return self._meta.capacity

    @property
    def AvailableCapacity(self) -> int:
        return self._meta.capacity - len(self.LoadIds)

    @property
    def LoadPositions(self) -> Dict[int, UniqueIdentifier]:
        return {ii: x for ii, x in enumerate(self._channel.State)}

    @property
    def Id(self) -> UniqueIdentifier:
        return self._id

    @property
    def Meta(self) -> dcs.LocationMeta:
        return self._meta

    @property
    def LoadIds(self) -> List[UniqueIdentifier]:
        return self._channel.StoredIds

    def get_removable_positions(self):
        return self._channel.get_removable_positions()

    def get_addable_positions(self):
        return self._channel.get_addable_positions()

    def get_removable_load_ids(self):
        return self._channel.get_removable_ids()

    def store_loads(self, load_ids: Iterable[UniqueIdentifier]):
        logger.info(f"Storing loads {[x for x in load_ids]} in location \'{self._id}\': {str(self._channel)}")
        self._channel.store(load_ids)
        logger.info(f"Done storing loads {[x for x in load_ids]} in location \'{self._id}\': {str(self._channel)}")
        return self

    def remove_loads(self, load_ids: Iterable[UniqueIdentifier]):
        logger.info(f"Removing loads {[x for x in load_ids]} from location \'{self._id}\': {str(self._channel)}")
        self._channel.remove(load_ids)
        logger.info(f"Done removing loads {[x for x in load_ids]} from location \'{self._id}\': {str(self._channel)}")
        return self

    def clear_loads(self):
        self._channel.clear()

    def set_reservation_token(self, token: uuid.UUID):
        self._reservation_token = token

    def remove_reservation_token(self, token: uuid.UUID):
        if self._reservation_token == token:
            self._reservation_token = None

    @property
    def Reserved(self) -> bool:
        return self._reservation_token is not None

    def verify_removable(self, load_id: UniqueIdentifier):
        return self._meta.channel_processor.verify_removable(load_id, state=self._channel.State)

    def summary(self) -> Dict[UniqueIdentifier, List[UniqueIdentifier]]:
        return {k.Id: [ld.id for ld in v] for k, v in self.LocLoads.items()}

    def __repr__(self):
        return f"{self._id}: {self.LoadIds}"

    def get_id(self) -> UniqueIdentifier:
        return self._id
if __name__ == "__main__":
    import coopstorage.storage2.loc_load.channel_processors as cps
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
    l_a.store_loads([lpn1.id])
    l_a.store_loads([lpn2.id])
    l_a.remove_loads([lpn2.id])
