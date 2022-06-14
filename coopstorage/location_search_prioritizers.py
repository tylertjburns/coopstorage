from coopstorage.my_dataclasses import Location, LocInvState, UoM, ResourceUoM
from typing import List

def by_space_available(loc_states: List[LocInvState], uom: UoM, smallest_first: bool = True) -> Location:
    loc_states.sort(key=lambda x: x.space_at_location(uom=uom), reverse=not smallest_first)

    return next(iter(
        [x.location for x in loc_states]
    ))

def by_content_present(loc_states: List[LocInvState], ru: ResourceUoM, smallest_first: bool = True) -> Location:
    loc_states.sort(key=lambda x: x.qty_resource_uom(resource_uom=ru), reverse=not smallest_first)

    return next(iter(
        [x.location for x in loc_states]
    ))