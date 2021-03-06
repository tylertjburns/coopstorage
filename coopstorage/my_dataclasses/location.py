from dataclasses import dataclass, field
from coopstorage.my_dataclasses import UoMCapacity, Resource, UoM
from typing import Dict, Optional, List, Union
import uuid
from coopstorage.resolvers import try_resolve_guid


@dataclass(frozen=True, slots=True)
class Location:
    uom_capacities: frozenset[UoMCapacity] = field(default_factory=frozenset)
    #TODO: Change this to a whitelist/blacklist set of lists
    resource_limitations: frozenset[Resource] = field(default_factory=frozenset)
    id: Optional[Union[str, uuid.UUID]] = None

    def __post_init__(self):
        if self.id is None: object.__setattr__(self, 'id', uuid.uuid4())

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return hash(self) == hash(other)

    @property
    def UoMCapacities(self) -> Dict[UoM, float]:
        return {x.uom: x.capacity for x in self.uom_capacities}

    def as_dict(self):
        return {
            'id': str(self.id),
            'uom_capacities': [x.as_dict() for x in self.uom_capacities],
            'resource_limitations': [x.as_dict() for x in self.resource_limitations]
        }

def location_factory(location: Location = None,
                     uom_capacities: frozenset[UoMCapacity] = None,
                     new_uom_capacities: List[UoMCapacity] = None,
                     removed_uom_capacities: List[UoMCapacity] = None,
                     resource_limitations: frozenset[Resource] = None,
                     new_resource_limitations: List[Resource] = None,
                     removed_resource_limitations: List[Resource] = None,
                     id: Union[str, uuid.UUID] = None) -> Location:

    uom_capacities = uom_capacities if uom_capacities is not None else \
                    (location.uom_capacities if location else None) or frozenset()

    if new_uom_capacities:
        existing = [x for x in list(uom_capacities) if x.uom not in [u.uom for u in new_uom_capacities]]
        uom_capacities = frozenset(existing + new_uom_capacities)

    if removed_uom_capacities:
        uom_capacities = set(uom_capacities)
        uom_capacities.difference_update(removed_uom_capacities)
        uom_capacities = frozenset(uom_capacities)

    resource_limitations = resource_limitations if resource_limitations is not None else \
            (location.resource_limitations if location else None) or frozenset()

    if new_resource_limitations:
        resource_limitations = frozenset(list(resource_limitations) + new_resource_limitations)

    if removed_resource_limitations:
        resource_limitations = set(resource_limitations)
        resource_limitations.difference_update(removed_resource_limitations)
        resource_limitations = frozenset(resource_limitations)

    id = try_resolve_guid(id) or (location.id if location else None) or uuid.uuid4()

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

if __name__ == "__main__":
    from dataclasses import asdict

    loc = location_factory()

    print(asdict(loc))