from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Tuple, Union
from coopstorage.my_dataclasses import Location, Content, ResourceUoM, UnitOfMeasure, Resource, content_factory, merge_content, LocInvState, UoMCapacity, ContainerState
import uuid
from pprint import pprint
from coopstorage.exceptions import *
import coopstorage.eventDefinition as cevents
from coopstorage.enums import ChannelType

location_prioritizer = Callable[[List[LocInvState]], Location]


# @dataclass(frozen=True, slots=True) #pydantic doesnt support slots
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
        return f"StorageState(id: {self.id}, Locs: {len(self.Inventory)}, occupied: {len(self.OccupiedLocs)}, empty: {len(self.EmptyLocs)})"

    def as_dict(self):
        return {
            f'{self.id=}'.split('=')[0].replace('self.', ''): str(self.id),
            f'{self.loc_states=}'.split('=')[0].replace('self.', ''): {str(x.location.id): x.as_dict() for x in self.loc_states}
        }

    def print(self):
        pprint(self.as_dict())

    def content_at_location(self,
                            location: Location,
                            resource_uom_filter: List[ResourceUoM] = None,
                            uom_filter: List[UnitOfMeasure] = None,
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

    def qty_uom_at_location(self, location: Location, uom: UnitOfMeasure):
        qty = sum([x.qty for x in self.content_at_location(location, uom_filter=[uom])])
        return qty

    def space_at_locations(self, resource_uom: ResourceUoM, locations: List[Location] = None) -> Dict[Location, float]:
        ret = {}

        if locations is None:
            locations = self.Locations

        for location in locations:
            ret[location] = self._loc_to_state_map[location].space_at_location(resource_uom)

        return ret

    def loc_state_matches(self,
                          resource_uoms: List[ResourceUoM] = None,
                          uom_capacities: List[UnitOfMeasure] = None,
                          loc_resource_limits: List[Resource] = None,
                          location_range: List[Location] = None,
                          space_avail_for_ru: Tuple[ResourceUoM, float] = None,
                          has_content: Content = None,
                          has_container: ContainerState = None,
                          channel_types: List[ChannelType] = None) -> List[LocInvState]:
        # start with all states
        matches = list(self.loc_states)

        # filter by the specified location range
        if location_range:
            matches = [state for state in matches if state.location in location_range]

        # filter by channel type
        if channel_types:
            matches = [state for state in matches if state.location.channel_type in channel_types]


        # filter by locations that match the provided uom capacities
        if uom_capacities:
            matches = [state for state in matches
                       if all(x in state.location.UoMCapacities.keys() for x in uom_capacities)]

        # filter by locations that have the provided resource uoms
        if resource_uoms:
            matches = [state for state in matches
                       if any(c.resourceUoM in resource_uoms for c in self.Inventory[state.location])]

        # filter by locations that match the provided resource limitations
        if loc_resource_limits:
            matches = [state for state in matches
                       if not state.location.resource_limitations or all(x in state.location.resource_limitations
                                                           for x in loc_resource_limits)]

        # filter by locations with open space
        if space_avail_for_ru:
            space_at_matches = self.space_at_locations(resource_uom=space_avail_for_ru[0],
                                                       locations=[x.location for x in matches])
            matches = [state for state in matches if space_at_matches[state.location] >= space_avail_for_ru[1]]

        # filter by locations with content exceeding has_content
        if has_content:
            matches = [state for state in matches
                       if state.QtyResourceUoMs.get(has_content.resourceUoM, 0) >= has_content.qty]

        # filter by locations with container
        if has_container:
            matches = [state for state in matches if has_container in state.containers]

        return matches

    def space_for_resource_uoms(self,
                                resource_uoms: List[ResourceUoM],
                                only_designated: bool = True) -> Dict[ResourceUoM, float]:
        if not only_designated:
            raise NotImplementedError()

        ret = {}
        for resource_uom in resource_uoms:
            loc_states = self.loc_state_matches(loc_resource_limits=[resource_uom.resource])
            available_space = sum(
                [space for loc, space in self.space_at_locations(locations=[x.location for x in loc_states], resource_uom=resource_uom.uom).items()])
            ret[resource_uom] = available_space
        return ret

    def capacity_for_resource_uoms(self,
                                   resource_uoms: List[ResourceUoM],
                                   only_designated: bool = True) -> Dict[ResourceUoM, float]:
        if not only_designated:
            raise NotImplementedError()

        ret = {}
        for resource_uom in resource_uoms:
            loc_states = self.loc_state_matches(loc_resource_limits=[resource_uom.resource])
            capacity = sum(
                [loc_state.location.UoMCapacities[resource_uom.uom] for loc_state in loc_states]
            )

            ret[resource_uom] = capacity
        return ret

    def find_location_with_content(self,
                                   content: Content,
                                   prioritizer: location_prioritizer = None) -> Location:
        matches = self.loc_state_matches(has_content=content)

        # handle no location found
        if len(matches) == 0:
            raise cevents.StorageException(
                args=cevents.OnNoLocationToRemoveContentExceptionEventArgs(
                    storage_state=self,
                    content=content
                )
            )

        # return location prioritized from list
        if prioritizer:
            return prioritizer(matches)

        # return first entry in matches
        return next(iter([x.location for x in matches]))

    def find_location_for_content(self,
                                  content: Content,
                                  prioritizer: location_prioritizer = None) -> Location:
        # locs matching required uom and resource limitation
        matches = self.loc_state_matches(uom_capacities=[content.UoM],
                                         loc_resource_limits=[content.Resource],
                                         space_avail_for_ru=(content.resourceUoM, content.qty),
                                         channel_types=[ChannelType.MERGED_CONTENT])

        # raise if no matches have space
        if len(matches) == 0:
            raise cevents.StorageException(
                args=cevents.OnNoLocationWithCapacityExceptionEventArgs(
                    storage_state=self,
                    content=content,
                    loc_uom_space_avail=self.space_at_locations(resource_uom=content.resourceUoM),
                    loc_states=list(self.loc_states)
                )
            )

        # return location prioritized from list
        if prioritizer:
            return prioritizer(matches)

        # return first entry in matches
        return next(iter([x.location for x in matches]))

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
    def Inventory(self) -> Dict[Location, Tuple[List[Content], List[ContainerState]]]:
        return {x.location: (x.location_container.contents, x.containers) for x in self.loc_states}

    @property
    def OccupiedLocs(self) -> List[Location]:
        return [state.location for state in self.loc_states if state.Occupied]

    @property
    def EmptyLocs(self) -> List[Location]:
        return [state.location for state in self.loc_states if not state.Occupied]

    @property
    def InventoryByResourceUom(self) -> Dict[ResourceUoM, float]:
        return self.qty_of_resource_uoms()

    @property
    def Locations(self) -> List[Location]:
        return list(self.Inventory.keys())

    # @property
    # def ActiveDesignations(self) -> Dict[Location, List[UnitOfMeasure]]:
    #     return {x.location: list(x.ActiveUoMDesignations) for x in self.loc_states}

    @property
    def LocInvStateByLocation(self) -> Dict[Location, LocInvState]:
        return {x.location: x for x in self.loc_states}

    @property
    def ResourceUoMManifest(self) -> List[ResourceUoM]:
        return list(self.InventoryByResourceUom.keys())


def storage_state_factory(storage_state: StorageState = None,
                          id: Union[str, uuid.UUID] = None,
                          all_loc_states: List[LocInvState] = None,
                          updated_locinv_states: List[LocInvState] = None,
                          added_locations: List[Location] = None,
                          removed_locations: List[Location] = None
                          ) -> StorageState:
    try:
        id = uuid.UUID(id)
    except:
        id = id or (storage_state.id if storage_state else None) or uuid.uuid4()


    loc_states = all_loc_states or (list(storage_state.loc_states) if storage_state else None) or []

    if updated_locinv_states:
        updated_dict = {x.location: x for x in updated_locinv_states}
        loc_states = frozenset([updated_dict.get(x.location, x) for x in loc_states])

    if added_locations:
        loc_states = frozenset(list(loc_states) + [LocInvState(x) for x in added_locations])

    if removed_locations:
        lookup = {x.location: x for x in loc_states}
        [lookup.pop(x) for x in removed_locations]
        loc_states = frozenset(lookup.values())

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




