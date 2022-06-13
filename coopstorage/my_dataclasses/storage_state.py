from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from coopstorage.my_dataclasses import Location, Content, ResourceUoM, UoM, Resource, content_factory, merge_content, LocInvState
import uuid
from pprint import pprint
from coopstorage.exceptions import *

location_prioritizer = Callable[[List[Location]], Location]

@dataclass(frozen=True)
class StorageState:
    loc_states: frozenset[LocInvState]
    id: str = uuid.uuid4()
    _loc_to_state_map: Dict[Location, LocInvState] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, '_loc_to_state_map', {x.location: x for x in self.loc_states})

    def __getitem__(self, item: Location):
        return self._loc_to_state_map[item]

    def __str__(self):
        return f"id: {self.id}, Locs: {len(self.Inventory)}, occupied: {len(self.OccupiedLocs)}, empty: {len(self.EmptyLocs)}"

    def print(self):
        pprint(self.Inventory)

    def content_at_location(self,
                            location: Location,
                            resource_uom_filter: List[ResourceUoM] = None,
                            uom_filter: List[UoM] = None,
                            aggregate: bool=False) -> List[Content]:
        if location not in self.Locations:
            raise ValueError(f"Location {location} not in storage {self.id}")

        content = self.LocInvStateByLocation[location].content(resource_uom_filter=resource_uom_filter,
                                                               uom_filter=uom_filter)

        if aggregate:
            content = merge_content(content)

        return content

    def content_by_location(self,
                            location_filter: List[Location] = None,
                            resource_uom_filter: List[ResourceUoM] = None,
                            aggregate: bool = False,
                            ) -> Dict[Location, List[Content]]:
        if location_filter is None:
            location_filter = self.Locations

        # default the ret to at least include everything in location_filter param
        ret = {loc: [] for loc in location_filter}

        # gather content at locations
        for loc in location_filter:
            ret[loc] = self.content_at_location(location=loc,
                                                resource_uom_filter=resource_uom_filter,
                                                aggregate=aggregate)

        return ret

    def qty_resource_uom_at_location(self, location: Location, resource_uom: ResourceUoM):
        qty = sum([x.qty for x in self.content_at_location(location, resource_uom_filter=[resource_uom], )])
        return qty

    def qty_uom_at_location(self, location: Location, uom: UoM):
        qty = sum([x.qty for x in self.content_at_location(location, uom_filter=[uom])])
        return qty

    def space_at_locations(self, uom: UoM, locations: List[Location] = None) -> Dict[Location, float]:
        ret = {}

        content_by_location = self.content_by_location(location_filter=locations, aggregate=True)

        for location, content_at_loc in content_by_location.items():
            if self.ActiveDesignations[location] in [[], None, uom]:
                ret[location] = location.UoMCapacities[uom] - sum(x.qty for x in content_at_loc)
            else:
                ret[location] = 0

        return ret

    def location_match(self,
                       resource_uoms: List[ResourceUoM] = None,
                       required_uom_types: List[UoM] = None,
                       loc_resource_limits: List[Resource] = None,
                       location_range: List[Location] = None) -> List[Location]:
        matches = [loc for loc in self.Inventory.keys()]

        if location_range:
            matches = [loc for loc in matches if loc in location_range]

        if required_uom_types:
            matches = [loc for loc in matches
                       if all(x in loc.UoMCapacities.keys() for x in required_uom_types)]

        if resource_uoms:
            matches = [loc for loc in matches
                       if any(c.resourceUoM in resource_uoms for c in self.Inventory[loc])]

        if loc_resource_limits:
            matches = [loc for loc in matches
                       if not loc.resource_limitations or all(x in loc.resource_limitations
                                                           for x in loc_resource_limits)]

        return matches

    def space_for_resource_uom(self,
                               resource_uoms: List[ResourceUoM],
                               only_designated: bool = True) -> Dict[ResourceUoM, float]:
        if not only_designated:
            raise NotImplementedError()

        ret = {}
        for resource_uom in resource_uoms:
            locs = self.location_match(loc_resource_limits=[resource_uom.resource])
            available_space = sum(
                [space for loc, space in self.space_at_locations(locations=locs, uom=resource_uom.uom).items()])
            ret[resource_uom] = available_space
        return ret

    def find_open_location(self, content: Content, prioritizer: location_prioritizer = None) -> Location:
        # locs matching required uom and resource limitation
        uom_resource_matches = self.location_match(required_uom_types=[content.uom], loc_resource_limits=[content.resource])

        if len(uom_resource_matches) == 0:
            raise NoLocationFoundException(storage_state=self)

        # locations with capacity
        space_at_matches = self.space_at_locations(uom=content.uom, locations=uom_resource_matches)
        matches = [loc for loc in uom_resource_matches if space_at_matches[loc] >= content.qty]

        # raise if no matches have space
        if len(matches) == 0:
            raise NoLocationWithCapacityException(content=content,
                                                  resource_uom_space=self.space_for_resource_uom(
                                                      resource_uoms=[content.resourceUoM])[content.resourceUoM],
                                                  loc_uom_space_avail=space_at_matches,
                                                  loc_states=self.loc_states,
                                                  storage_state=self
                                                  )

        # return location prioritized from list
        if prioritizer:
            return prioritizer(matches)

        # return first entry in matches
        return next(iter(matches))

    def qty_of_resource_uoms(self,
                             resource_uoms: List[ResourceUoM] = None,
                             location_range: List[Location] = None) -> Dict[ResourceUoM, float]:
        content_by_loc = self.content_by_location(location_filter=location_range, resource_uom_filter=resource_uoms)

        # default the ret to at least include everything in resource_uoms param
        ret = {x: 0 for x in resource_uoms} if resource_uoms else {}

        # accumulate the qty of resource uoms
        for loc, c_lst in content_by_loc.items():
            for c in c_lst:
                if resource_uoms and c.resourceUoM not in resource_uoms:
                    continue
                ret.setdefault(c.resourceUoM, 0)
                ret[c.resourceUoM] += c.qty

        return ret

    @property
    def Inventory(self) -> Dict[Location, List[Content]]:
        return {x.location: list(x.contents) for x in self.loc_states}

    @property
    def OccupiedLocs(self) -> List[Location]:
        return [loc for loc, cont in self.Inventory.items() if len(cont) > 0]

    @property
    def EmptyLocs(self) -> List[Location]:
        return [loc for loc, cont in self.Inventory.items() if len(cont) == 0]

    @property
    def InventoryByResourceUom(self) -> Dict[ResourceUoM, float]:
        return self.qty_of_resource_uoms()

    @property
    def Locations(self) -> List[Location]:
        return list(self.Inventory.keys())

    @property
    def ActiveDesignations(self) -> Dict[Location, List[UoM]]:
        return {x.location: list(x.ActiveUoMDesignations) for x in self.loc_states}

    @property
    def LocInvStateByLocation(self) -> Dict[Location, LocInvState]:
        return {x.location: x for x in self.loc_states}

def storage_state_factory(storage_state: StorageState = None,
                          id: str = None,
                          all_loc_states: List[LocInvState] = None,
                          updated_loc_states: List[LocInvState] = None
                          ) -> StorageState:
    id = id or (storage_state.id if storage_state else None) or uuid.uuid4()


    all_loc_states = all_loc_states or (list(storage_state.loc_states) if storage_state else None) or []
    updated_dict = {x.location: x for x in updated_loc_states}
    loc_states = frozenset([updated_dict.get(x.location, x) for x in all_loc_states])

    return StorageState(
        id=id,
        loc_states=loc_states
    )

if __name__ == "__main__":


    loc_inv_states = [
        LocInvState(
            Location(id=str(x))
        )
        for x in range(10)]


    ss = StorageState(
        loc_states=frozenset(loc_inv_states)
    )

    ss.print()




