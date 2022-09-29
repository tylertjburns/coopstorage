from coopstorage.my_dataclasses import Location, Content, ResourceUoM, merge_content, UoM, location_factory, UoMCapacity, Resource, content_factory, Container, container_factory
from dataclasses import dataclass, field
from typing import List, Tuple
from coopstorage.enums import ChannelType
from cooptools.common import flattened_list_of_lists

@dataclass(frozen=True, slots=True)
class LocInvState:
    location: Location
    containers: frozenset[Container] = field(default_factory=frozenset)

    def find_containers(self,
                uom_filter: List[UoM] = None,
                only_extractable: bool = False) -> List[Container]:
        if only_extractable:
            ret = self.ExtractableContainers
        else:
            ret = self.containers

        if uom_filter:
            ret = [x for x in ret if x.uom in uom_filter]

        return ret

    def content(self,
                resource_uom_filter: List[ResourceUoM] = None,
                uom_filter: List[UoM] = None,
                aggregate: bool = True,
                only_extractable: bool = False) -> List[Content]:

        if only_extractable:
            relevant_cntnrs = self.ExtractableContainers
        else:
            relevant_cntnrs = self.containers
        ret = flattened_list_of_lists([x.contents for x in relevant_cntnrs])

        if resource_uom_filter:
            ret = [x for x in ret if x.resourceUoM in resource_uom_filter]

        if uom_filter:
            ret = [x for x in ret if x.resourceUoM.uom in uom_filter]

        if aggregate:
            ret = merge_content(ret)

        return ret

    def qty_resource_uom(self, resource_uom: ResourceUoM) -> float:
        qty = sum([x.qty for x in self.content(resource_uom_filter=[resource_uom])])
        return qty

    def qty_uom(self, uom: UoM) -> float:
        qty = len([x for x in self.find_containers(uom_filter=[uom])])
        return qty

    def space_at_location(self, uom: UoM):
        if (self.ActiveUoMDesignations in [[], None]) or \
                uom in self.ActiveUoMDesignations:
            return self.location.UoMCapacities[uom] - len([x for x in self.find_containers(uom_filter=[uom])])
        else:
            return 0

    @property
    def ActiveUoMDesignations(self):
        return [x.uom for x in self.containers]

    @property
    def ExtractableContainers(self) -> List[Container]:
        if len(self.containers) == 0:
            return []
        elif self.location.channel_type == ChannelType.CONTAINER_ALL_ACCESSIBLE:
            return list(self.containers)
        elif self.location.channel_type == ChannelType.CONTAINER_FIFO_QUEUE:
            return [list(self.containers)[0]]
        elif self.location.channel_type == ChannelType.CONTAINER_LIFO_QUEUE:
            return [list(self.containers)[-1]]
        else:
            raise NotImplementedError(f"No implementation for {self.location.channel_type}")

def loc_inv_state_factory(
        loc_inv_state: LocInvState = None,
        location: Location = None,
        location_content: List[Content] = None,
        location_channel_type: ChannelType = None,
        location_coords: Tuple[float, ...] = None,
        containers: frozenset[Container] = None,
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
                                channel_type=location_channel_type,
                                coords=location_coords,
                                contents=location_content,
                                id=loc_id)
    _containers = containers if containers is not None else \
        (loc_inv_state.containers if loc_inv_state else None) or frozenset()

    return LocInvState(
        location=_location,
        containers=_containers
    )
