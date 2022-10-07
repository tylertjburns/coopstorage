from dataclasses import dataclass, field
from coopstorage.my_dataclasses import UoMCapacity, Resource, UnitOfMeasure, ContainerState, container_factory, Content
from typing import Dict, Optional, List, Union, Tuple
import uuid
from coopstorage.resolvers import try_resolve_guid
from coopstorage.enums import ChannelType
from coopstorage.constants import *

@dataclass(frozen=True, slots=True)
class Location:
    uom_capacities: frozenset[UoMCapacity] = field(default_factory=frozenset)
    #TODO: Change this to a whitelist/blacklist set of lists
    resource_limitations: frozenset[Resource] = field(default_factory=frozenset)
    id: Optional[Union[str, uuid.UUID]] = None
    coords: Tuple[float, ...] = None
    channel_type: ChannelType = ChannelType.ALL_ACCESSIBLE
    max_resources_uoms: int = 1

    def __post_init__(self):
        if self.id is None:
            object.__setattr__(self, f'{self.id=}'.split('=')[0].replace('self.', ''), uuid.uuid4())

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return hash(self) == hash(other)

    @property
    def UoMCapacities(self) -> Dict[UnitOfMeasure, float]:
        return {x.uom: x.capacity for x in self.uom_capacities}

    def as_dict(self):
        return {
            f'{self.id=}'.split('=')[0].replace('self.', ''): str(self.id),
            f'{self.uom_capacities=}'.split('=')[0].replace('self.', ''): [x.as_dict() for x in self.uom_capacities],
            f'{self.resource_limitations=}'.split('=')[0].replace('self.', ''): [x.as_dict() for x in self.resource_limitations],
            f'{self.coords=}'.split('=')[0].replace('self.', ''): str(self.coords),
            f'{self.channel_type=}'.split('=')[0].replace('self.', ''): str(self.channel_type),
            f'{self.max_resources_uoms=}'.split('=')[0].replace('self.', ''): str(self.max_resources_uoms),
        }

def location_factory(location: Location = None,
                     uom_capacities: frozenset[UoMCapacity] = None,
                     new_uom_capacities: List[UoMCapacity] = None,
                     removed_uom_capacities: List[UoMCapacity] = None,
                     resource_limitations: frozenset[Resource] = None,
                     new_resource_limitations: List[Resource] = None,
                     removed_resource_limitations: List[Resource] = None,
                     channel_type: ChannelType = None,
                     coords: Tuple[float, ...] = None,
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

    channel_type = channel_type or (location.channel_type if location else None) or ChannelType.ALL_ACCESSIBLE

    coords = coords or (location.coords if location else None)

    return Location(
        resource_limitations=resource_limitations,
        uom_capacities=uom_capacities,
        id=id,
        channel_type=channel_type,
        coords=coords
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