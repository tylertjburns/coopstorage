from cooptools.geometry_utils.vector_utils import FloatVec, IterVec
import coopstorage.my_dataclasses as dcs
from coopstorage.storage2.loc_load.types import *
from dataclasses import dataclass, field
from coopstorage.my_dataclasses import UoMCapacity, Resource
from typing import Dict, Optional, List, Union, Tuple
import uuid
from coopstorage.enums import ChannelType


@dataclass(frozen=True, slots=True)
class Load:
    id: Optional[UniqueId] = field(default_factory=uuid.uuid4)
    uom: dcs.UnitOfMeasure = field(default_factory=lambda: dcs.UnitOfMeasure(name='EA'))

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return hash(self) == hash(other)

@dataclass(frozen=True, slots=True)
class LoadLocation:
    coords: FloatVec
    id: Optional[UniqueId] = field(default_factory=uuid.uuid4)
    uom_capacities: frozenset[dcs.UoMCapacity] = field(default_factory=frozenset)
    is_controlled: bool = True

@dataclass(frozen=True, slots=True)
class LoadPosition:
    coords: FloatVec
    boundary: IterVec


@dataclass(frozen=True, slots=True)
class TransferRequest:
    load_id: UniqueId
    source_loc_id: UniqueId
    dest_loc_id: UniqueId

@dataclass(frozen=True, slots=True)
class LocationMeta:
    coords: FloatVec = None
    channel_processor: ChannelType = ChannelType.ALL_ACCESSIBLE
    max_resources_uoms: int = 1
    boundary: IterVec = None



if __name__ == "__main__":
    from pprint import pprint

    l1 = Load(lpn=1)
    l2 = Load(lpn=2)
    l3 = Load(lpn=3)
    l4 = Load(lpn=3)

    def test_1():
        ls = LoadStorage()
        ls.add_loads([l1, l2, l3, l4])

        pprint(ls.Loads)

        ls.remove_loads(ids=[2])

        pprint(ls.Loads)
    test_1()