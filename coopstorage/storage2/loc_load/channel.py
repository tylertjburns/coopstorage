import uuid
import logging
import coopstorage.storage2.loc_load.channel_processors as cps
from typing import Protocol, List, Optional, Iterable, Dict
from cooptools.protocols import UniqueIdentifier
from cooptools.dataStore.dataStoreProtocol import DataStoreProtocol
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class ChannelMeta:
    id: UniqueIdentifier
    processor_type: cps.IChannelProcessor
    capacity: int

class ChannelStateStore:
    def __init__(self,
                 data_store: DataStoreProtocol):
        self._data_store = data_store

    def retrieve_state(self):
        return self._data_store.get(ids=[self._id])

    # def persist_state(self, ):
    #     self._data_store.


class Channel:
    def __init__(self,
                 processor: cps.IChannelProcessor,
                 id: UniqueIdentifier = None,
                 capacity: int = 1,
                 init_state: Dict[int, UniqueIdentifier] = None
                 ):
        self._id = id or uuid.uuid4()
        self._processor: cps.IChannelProcessor = processor
        self._capacity: int = capacity
        self._state: List[Optional[UniqueIdentifier]] = [None for _ in range(self._capacity)]

        if init_state is not None:
            for ind, val in init_state.items():
                self._state[ind] = val

    def store(self,
             ids: Iterable[UniqueIdentifier]):
        logger.info(f"Adding channel contents: {self._id}")
        self._state = self._processor.process(state=self._state, added=ids)
        logger.info(f"Done adding channel contents: {self._id}")
        return self


    def remove(self,
               ids: Iterable[UniqueIdentifier]):
        logger.info(f"Removing channel contents: {self._id}")
        self._state = self._processor.process(state=self._state, removed=ids)
        logger.info(f"Done removing channel contents: {self._id}")
        return self

    def clear(self):
        logger.info(f"Clearing channel contents: {self._id}")
        while True:
            removable = self.get_removable_ids()
            if len(removable) == 0:
                break
            self._state = self._processor.process(state=self._state, removed=removable[0])

        if len(self.StoredIds) > 0:
            raise ValueError(f'Should have cleared loads, but load remains')
        logger.info(f"Done clearing channel contents: {self._id}")

    @property
    def State(self) -> List[Optional[UniqueIdentifier]]:
        return self._state

    @property
    def PopulatedIdxs(self) -> Dict[int, UniqueIdentifier]:
        ret = {}
        for ii, val in enumerate(self._state):
            if val is not None:
                ret[ii] = val

        return ret

    @property
    def StoredIds(self) -> List[UniqueIdentifier]:
        return [x for x in self._state if x is not None]

    def get_removable_ids(self):
        return self._processor.get_removeable_ids(self._state)

    def get_removable_positions(self):
        return self._processor.get_removable_positions(self._state)

    def get_addable_positions(self):
        return self._processor.get_addable_positions(self._state)

    def __repr__(self):
        return f"{self._id}: " + cps.str_format_channel_state(self._state)

if __name__ == "__main__":
    from pprint import pprint
    from cooptools.common import LETTERS

    def test_basic_channel_usage():
        channel = Channel(
            processor=cps.LIFOFlowBackwardChannelProcessor(),
            capacity=5
        )

        channel.store(ids=[1])

        pprint(channel.State)

        channel.store(ids=[2])
        pprint(channel.State)

        channel.remove(ids=[2])
        pprint(channel.State)

    def test_add_too_many_loads():
        channel = Channel(
            processor=cps.LIFOFlowBackwardChannelProcessor(),
            capacity=5
        )
        for ii in range(10):
            channel.store([LETTERS[ii]])
            pprint(channel)

    def test_FIFO_flow():
        """arrange"""
        channel = Channel(
            processor=cps.FIFOFlowChannelProcessor(),
            capacity=5
        )

        """act"""
        for ii in range(3):
            channel.store([LETTERS[ii]])

        channel.remove([LETTERS[0]])

        for ii in range(3):
            channel.store([LETTERS[ii+3]])

        """assert"""
        pprint(channel)



    # test_add_too_many_loads()
    test_FIFO_flow()