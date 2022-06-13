from coopstorage.my_dataclasses import Location, Content, ResourceUoM, merge_content, UoM, location_factory, UoMCapacity, Resource, content_factory
from dataclasses import dataclass, field
from typing import List

@dataclass(frozen=True)
class LocInvState:
    location: Location
    contents: frozenset[Content] = field(default_factory=frozenset)

    def content(self,
                resource_uom_filter: List[ResourceUoM] = None,
                uom_filter: List[UoM] = None,
                aggregate: bool = True) -> List[Content]:
        ret = self.contents
        if resource_uom_filter:
            ret = [x for x in self.contents if x.resourceUoM in resource_uom_filter]

        if uom_filter:
            ret = [x for x in self.contents if x.resourceUoM.uom in uom_filter]

        if aggregate:
            ret = merge_content(ret)

        return ret

    def qty_resource_uom(self, resource_uom: ResourceUoM) -> float:
        qty = sum([x.qty for x in self.content(resource_uom_filter=[resource_uom])])
        return qty

    def qty_uom(self, uom: UoM) -> float:
        qty = sum([x.qty for x in self.content(uom_filter=[uom])])
        return qty

    @property
    def ActiveUoMDesignations(self):
        return [x.uom for x in self.contents]

def loc_inv_state_factory(
        loc_inv_state: LocInvState = None,
        location: Location = None,
        contents: frozenset[Content] = None,
        loc_uom_capacities: frozenset[UoMCapacity] = None,
        loc_resource_limitations: frozenset[Resource] = None,
        loc_id: str = None
        ) -> LocInvState:

    _loc_uom_capacities = loc_uom_capacities if loc_uom_capacities is not None else \
                         (location.UoMCapacities if location else None) or \
                         (loc_inv_state.location.uom_capacities if loc_inv_state else None) or \
                         frozenset()

    _location = location or \
               (loc_inv_state.location if loc_inv_state else None) or \
               location_factory(uom_capacities=_loc_uom_capacities,
                                resource_limitations=loc_resource_limitations,
                                id=loc_id)
    _contents = contents if contents is not None else \
        (loc_inv_state.contents if loc_inv_state else None) or frozenset()

    return LocInvState(
        location=_location,
        contents=_contents
    )
