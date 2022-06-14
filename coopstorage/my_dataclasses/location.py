from dataclasses import dataclass, field
from coopstorage.my_dataclasses import UoMCapacity, Resource, UoM
from typing import Dict, Optional, List, Union
import uuid


@dataclass(frozen=True, slots=True)
class Location:
    uom_capacities: frozenset[UoMCapacity] = field(default_factory=frozenset)
    resource_limitations: frozenset[Resource] = field(default_factory=frozenset)
    id: Optional[Union[str, uuid.UUID]] = None

    def __post_init__(self):
        if self.id is None: object.__setattr__(self, 'id', uuid.uuid4())

    def __hash__(self):
        return hash(self.id)

    @property
    def UoMCapacities(self) -> Dict[UoM, float]:
        return {x.uom: x.capacity for x in self.uom_capacities}

def location_factory(location: Location = None,
                     uom_capacities: frozenset[UoMCapacity] = None,
                     resource_limitations: frozenset[Resource] = None,
                     id: Union[str, uuid.UUID] = None) -> Location:

    uom_capacities = uom_capacities if uom_capacities is not None else \
                    (location.uom_capacities if location else None) or frozenset()

    resource_limitations = resource_limitations if resource_limitations is not None else \
            (location.resource_limitations if location else None) or frozenset()

    id = id or (location.id if location else None) or uuid.uuid4()

    return Location(
        uom_capacities=uom_capacities,
        resource_limitations=resource_limitations,
        id=id
    )

def location_generation(
        loc_template_quantities: Dict[Location, int]
) -> List[Location]:
    ret = []

    for loc, n in loc_template_quantities.items():
        for ii in range(n):
            ret.append(location_factory(location=loc, id=uuid.uuid4()))

    return ret