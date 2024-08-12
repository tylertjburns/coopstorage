from cooptools.geometry_utils.vector_utils import FloatVec, IterVec
from dataclasses import dataclass, field, asdict
from coopstorage.my_dataclasses import UoMCapacity, Resource
from typing import Dict, Optional, List, Union, Tuple, Iterable
import uuid
from cooptools.geometry_utils import vector_utils as vec
import coopstorage.storage2.loc_load.channel_processors as cps
import re
from cooptools.protocols import UniqueIdentifier

@dataclass(frozen=True, slots=True)
class BaseDataClass:
    details: Optional[Dict] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class BaseIdentifiedDataClass(BaseDataClass):
    id: Optional[UniqueIdentifier] = field(default_factory=uuid.uuid4)

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return hash(other) == hash(self)

    def get_id(self):
        return self.id

@dataclass(frozen=True, slots=True, kw_only=True)
class UnitOfMeasure(BaseDataClass):
    name: str
    dimensions: vec.FloatVec = field(default_factory=lambda: vec.homogeneous_vector(3, 1))

@dataclass(frozen=True, slots=True, kw_only=True)
class Load(BaseIdentifiedDataClass):
    uom: UnitOfMeasure = field(default_factory=lambda: UnitOfMeasure(name='EA'))
    weight: float = None

@dataclass(frozen=True, slots=True, kw_only=True)
class LoadPosition(BaseIdentifiedDataClass):
    loc_offset: FloatVec
    uom_capacities: frozenset[UoMCapacity] = field(default_factory=frozenset)
    is_controlled: bool = True
    boundary: IterVec = field(default_factory=list)

@dataclass(frozen=True, slots=True)
class PatternMatchQuery:
    regex: str = None
    id: UniqueIdentifier = None

    def __post_init__(self):
        if self.regex is None and self.id is None:
            raise ValueError(f"At least one of regex or id must be filled")

        if self.id is not None:
            object.__setattr__(self, f'{self.regex=}'.split('=')[0].replace('self.', ''), str(self.id))

    def check_if_matches(self, value: str):
        return re.match(self.regex, value)

@dataclass(frozen=True, slots=True, kw_only=True)
class LocationMeta(BaseDataClass):
    dims: vec.FloatVec
    channel_processor: cps.IChannelProcessor = field(default=cps.AllAvailableChannelProcessor())
    boundary: IterVec = None
    capacity: int = 1


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