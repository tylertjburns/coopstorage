from cooptools.geometry_utils.vector_utils import FloatVec, IterVec
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List, Union, Tuple, Iterable, Self
import uuid
from cooptools.geometry_utils import vector_utils as vec
import coopstorage.storage2.loc_load.channel_processors as cps
import re
from cooptools.protocols import UniqueIdentifier
from cooptools.coopDataclass import BaseDataClass, BaseIdentifiedDataClass


@dataclass(frozen=True, slots=True, kw_only=True)
class Resource(BaseDataClass):
    name: str
    description: str = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UnitOfMeasure(BaseDataClass):
    name: str
    dimensions: vec.FloatVec = field(default_factory=lambda: vec.homogeneous_vector(3, 1))


@dataclass(frozen=True, slots=True, kw_only=True)
class UoMCapacity(BaseDataClass):
    uom: UnitOfMeasure
    capacity: float


@dataclass(frozen=True, slots=True, kw_only=True)
class LoadContent(BaseDataClass):
    resource: Resource
    uom: UnitOfMeasure
    qty: float

    def __post_init__(self):
        if self.qty < 0:
            raise ValueError(f"qty cannot be negative: {self.qty}")


@dataclass(frozen=True, slots=True, kw_only=True)
class Load(BaseIdentifiedDataClass):
    uom: UnitOfMeasure = field(default_factory=lambda: UnitOfMeasure(name='EA'))
    weight: float = None
    contents: frozenset = field(default_factory=frozenset)        # frozenset[LoadContent]
    uom_capacities: frozenset = field(default_factory=frozenset)  # frozenset[UoMCapacity]

@dataclass(frozen=True, slots=True, kw_only=True)
class LoadPosition(BaseIdentifiedDataClass):
    loc_offset: FloatVec
    uom_capacities: frozenset[UoMCapacity] = field(default_factory=frozenset)
    is_controlled: bool = True
    boundary: IterVec = field(default_factory=list)

@dataclass(frozen=True, slots=True, kw_only=True)
class LocationMeta(BaseDataClass):
    dims: vec.FloatVec
    channel_processor: cps.IChannelProcessor = field(default=cps.AllAvailableChannelProcessor())
    boundary: IterVec = None
    capacity: int = 1

    def __post_init__(self):
        if type(self.channel_processor) == str:
            object.__setattr__(self, 'channel_processor', cps.ChannelProcessorType.by_str(self.channel_processor).value)

    def to_jsonable_dict(self):
        ret = asdict(self)
        ret.update({'channel_processor': type(self.channel_processor).__name__})
        return ret

if __name__ == "__main__":
    from pprint import pprint

    l1 = Load(id=1)
    l2 = Load(id=2)
    l3 = Load(id=3)
    l4 = Load(id=4)

    def test_1():
        ls = ()
        ls.add_loads([l1, l2, l3, l4])

        pprint(ls.LoadIds)

        ls.remove_loads(ids=[2])

        pprint(ls.LoadIds)
    test_1()