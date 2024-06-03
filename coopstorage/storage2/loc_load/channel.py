import uuid

import coopstorage.storage2.loc_load.dcs as dcs
import coopstorage.storage2.loc_load.channel_processors as cps
from coopstorage.storage2.loc_load.qualifier import Qualifier
from typing import Protocol, List, Optional, Iterable
import cooptools.geometry_utils.vector_utils as vec
from coopstorage.storage2.loc_load.types import UniqueId


class Channel:
    def __init__(self,
                 processor: cps.IChannelProcessor,
                 # uom_qualifier: Qualifier,
                 id: UniqueId = None,
                 boundary: vec.IterVec = None,
                 capacity: int = 1,
                 init_loads: Iterable[dcs.Load] = None
                 ):
        self._id = id or uuid.uuid4()
        self._processor: cps.IChannelProcessor = processor
        # self._uom_qualifier: Qualifier = uom_qualifier
        self._capacity: int = capacity
        self._state: List[Optional[dcs.Load]] = [None for _ in range(self._capacity)]
        self.boundary: vec.IterVec = boundary

        if init_loads is not None:
            self.store(init_loads)

    def store(self,
             loads: Iterable[dcs.Load]):
        self._state = self._processor.process(state=self._state, added=loads)

    def remove(self,
               loads: Iterable[dcs.Load]):
        self._state = self._processor.process(state=self._state, removed=loads)

    @property
    def LoadState(self) -> List[Optional[dcs.Load]]:
        return self._state

    def __repr__(self):
        return f"{self._id}: " + ','.join([x.id if x is not None else '-' for x in self._state ])

if __name__ == "__main__":
    import coopstorage.my_dataclasses as storage_dcs
    from pprint import pprint
    from cooptools.common import LETTERS

    def test_basic_channel_usage():
        pallet = storage_dcs.UnitOfMeasure(name='Pallet01')
        l1 = dcs.Load(id='a', uom=pallet)
        l2 = dcs.Load(id='b', uom=pallet)
        channel = Channel(
            processor=cps.LIFOFlowBackwardChannelProcessor(),
            # uom_qualifier=Qualifier(eligibles=[pallet]),
            capacity=5
        )

        channel.store(loads=[l1])

        pprint(channel.LoadState)

        channel.store(loads=[l2])
        pprint(channel.LoadState)

        channel.remove(loads=[l2])
        pprint(channel.LoadState)

    def test_add_too_many_loads():
        pallet = storage_dcs.UnitOfMeasure(name='Pallet01')
        l1 = dcs.Load(id='a', uom=pallet)
        l2 = dcs.Load(id='b', uom=pallet)
        channel = Channel(
            processor=cps.LIFOFlowBackwardChannelProcessor(),
            # uom_qualifier=Qualifier(eligibles=[pallet]),
            capacity=5
        )
        for ii in range(10):
            channel.store([dcs.Load(id=LETTERS[ii], uom=pallet)])
            pprint(channel)

    def test_FIFO_flow():
        """arrange"""
        pallet = storage_dcs.UnitOfMeasure(name='Pallet01')
        channel = Channel(
            processor=cps.FIFOFlowChannelProcessor(),
            # uom_qualifier=Qualifier(eligibles=[pallet]),
            capacity=5
        )

        """act"""
        for ii in range(3):
            channel.store([dcs.Load(id=LETTERS[ii], uom=pallet)])

        channel.remove([dcs.Load(id=LETTERS[0], uom=pallet)])

        for ii in range(3):
            channel.store([dcs.Load(id=LETTERS[ii+3], uom=pallet)])

        """assert"""
        pprint(channel)



    # test_add_too_many_loads()
    test_FIFO_flow()