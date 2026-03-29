from cooptools.geometry_utils.vector_utils import FloatVec, IterVec
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List, Union, Tuple, Iterable, Self
import uuid
from cooptools.geometry_utils import vector_utils as vec
import coopstorage.storage2.loc_load.channel_processors as cps
from cooptools.protocols import UniqueIdentifier
from cooptools.coopDataclass import BaseDataClass, BaseIdentifiedDataClass


@dataclass(frozen=True, slots=True, kw_only=True)
class Resource(BaseIdentifiedDataClass):
    name: str
    description: str = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UnitOfMeasure(BaseIdentifiedDataClass):
    name: str
    dimensions: vec.FloatVec = field(default_factory=lambda: vec.homogeneous_vector(3, 1))


@dataclass(frozen=True, slots=True, kw_only=True)
class UoMCapacity(BaseDataClass):
    uom: UnitOfMeasure
    capacity: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ContainerContent(BaseIdentifiedDataClass):
    resource: Resource
    uom: UnitOfMeasure
    qty: float

    def __post_init__(self):
        if self.qty <= 0:
            raise ValueError(f"qty cannot be negative: {self.qty}")


@dataclass(frozen=True, slots=True, kw_only=True)
class Container(BaseIdentifiedDataClass):
    uom: UnitOfMeasure = field(default_factory=lambda: UnitOfMeasure(name='EA'))
    weight: float = None
    contents: frozenset = field(default_factory=frozenset)        # frozenset[ContainerContent]
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

    l1 = Container(id=1)
    l2 = Container(id=2)
    l3 = Container(id=3)
    l4 = Container(id=4)

    def test_1():
        ls = ()
        ls.add_containers([l1, l2, l3, l4])

        pprint(ls.ContainerIds)

        ls.remove_containers(ids=[2])

        pprint(ls.ContainerIds)
    test_1()