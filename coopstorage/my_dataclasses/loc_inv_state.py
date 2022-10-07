from coopstorage.my_dataclasses import Location, Content, ResourceUoM, merge_content, UnitOfMeasure, location_factory, UoMCapacity, Resource, content_factory, ContainerState, container_factory, BaseDC
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Union
from coopstorage.enums import ChannelType
from cooptools.common import flattened_list_of_lists
from coopstorage.constants import *

@dataclass(frozen=True, slots=True)
class LocInvState(BaseDC):
    location: Location
    containers: Tuple[ContainerState] = field(default_factory=tuple)
    location_container: ContainerState = None

    def __post_init__(self):
        if self.location_container is None:
            object.__setattr__(self,
                               f'{self.location_container=}'.split('=')[0].replace('self.', ''),
                               container_factory(lpn=f"{self.location.id}_CNTNR",
                                                      uom=UnitOfMeasure(name=LOCATION_CONTAINER_UOM_TYPE_NAME),
                                                      uom_capacities=self.location.uom_capacities)
                               )


    def as_dict(self):
        return {
            f'{self.location=}'.split('=')[0].replace('self.', ''): self.location.as_dict(),
            f'{self.containers=}'.split('=')[0].replace('self.', ''): [x.as_dict() for x in self.containers],
            f'{self.location_container=}'.split('=')[0].replace('self.', ''): self.location_container.as_dict(),
        }


    def find_containers(self,
                        uom_filter: List[UnitOfMeasure] = None,
                        only_extractable: bool = False) -> List[ContainerState]:
        if only_extractable:
            ret = self.ExtractableContainers
        else:
            ret = self.containers

        if uom_filter:
            ret = [x for x in ret if x.uom in uom_filter]

        return ret

    def content(self,
                resource_uom_filter: List[ResourceUoM] = None,
                uom_filter: List[UnitOfMeasure] = None,
                aggregate: bool = True,
                only_extractable: bool = False) -> List[Content]:

        if self.location.channel_type == ChannelType.MERGED_CONTENT:
            relevant_cntnrs = [self.location_container]
        elif only_extractable:
            relevant_cntnrs = self.ExtractableContainers
        else:
            relevant_cntnrs = self.containers

        ret = flattened_list_of_lists([list(x.contents) for x in relevant_cntnrs])

        if resource_uom_filter:
            ret = [x for x in ret if x.resourceUoM in resource_uom_filter]

        if uom_filter:
            ret = [x for x in ret if x.resourceUoM.uom in uom_filter]

        if aggregate:
            ret = merge_content(ret)

        return ret

    def space_at_location(self, resource_uom: ResourceUoM) -> float:
        ru_manifest = self.QtyResourceUoMs

        if resource_uom not in ru_manifest.keys() and len(ru_manifest.keys()) + 1 > self.location.max_resources_uoms:
            return 0

        if self.location.channel_type == ChannelType.MERGED_CONTENT:
            ret = self.location_container.SpaceForUoMs.get(resource_uom.uom, 0)
        else:
            ret = self.location.UoMCapacities.get(resource_uom.uom, 0) - len(self.find_containers(uom_filter=[resource_uom.uom]))

        return ret

    @property
    def ExtractableContainers(self) -> List[ContainerState]:
        if len(self.containers) == 0:
            return []
        elif self.location.channel_type == ChannelType.ALL_ACCESSIBLE:
            return list(self.containers)
        elif self.location.channel_type == ChannelType.FIFO_QUEUE:
            return [list(self.containers)[0]]
        elif self.location.channel_type == ChannelType.LIFO_QUEUE:
            return [list(self.containers)[-1]]
        else:
            raise NotImplementedError(f"No implementation for {self.location.channel_type}")


    @property
    def QtyLocContentResourceUoMs(self) -> Dict[ResourceUoM, float]:
        ret = {}
        for c in self.location_container.contents:
            ret.setdefault(c.resourceUoM, 0)
            ret[c.resourceUoM] += c.qty

        return ret

    @property
    def QtyLocContentUoMs(self) -> Dict[UnitOfMeasure, float]:
        ret = {}
        for c in self.location_container.contents:
            ret.setdefault(c.UoM, 0)
            ret[c.UoM] += c.qty

        return ret

    @property
    def QtyContainerContentUoMs(self) -> Dict[UnitOfMeasure, float]:
        ret = {}
        # accumulate the qty of resource uoms
        for cnt in self.containers:
            for c in cnt.contents:
                ret.setdefault(c.UoM, 0)
                ret[c.UoM] += c.qty


        return ret

    @property
    def QtyContainerContentResourceUoMs(self) -> Dict[ResourceUoM, float]:
        ret = {}
        # accumulate the qty of resource uoms
        for cnt in self.containers:
            for c in cnt.contents:
                ret.setdefault(c.resourceUoM, 0)
                ret[c.resourceUoM] += c.qty
        return ret

    @property
    def QtyContainerUoMs(self) -> Dict[UnitOfMeasure, float]:
        ret = {}
        # accumulate the qty of resource uoms
        for c in self.containers:
            ret.setdefault(c.UoM, 0)
            ret[c.UoM] += 1

        return ret

    @property
    def QtyContentUoMs(self) -> Dict[UnitOfMeasure, float]:
        loc_uoms = self.QtyLocContentUoMs
        cntnr_uoms = self.QtyContainerContentUoMs

        all_uoms = set(list(loc_uoms.keys()) + list(cntnr_uoms.keys()))

        ret = {x: loc_uoms.get(x, 0) + cntnr_uoms.get(x, 0) for x in all_uoms}

        return ret

    @property
    def QtyResourceUoMs(self) -> Dict[ResourceUoM, float]:
        loc_ruoms = self.QtyLocContentResourceUoMs
        cntnr_ruoms = self.QtyContainerContentResourceUoMs

        all_uoms = set(list(loc_ruoms.keys()) + list(cntnr_ruoms.keys()))

        ret = {x: loc_ruoms.get(x, 0) + cntnr_ruoms.get(x, 0) for x in all_uoms}

        return ret

    @property
    def Occupied(self) -> bool:
        return len(self.QtyResourceUoMs) > 0
        # if self.location.channel_type == ChannelType.MERGED_CONTENT:
        #     return len(self.location_container.contents) > 0
        # else:
        #     return len(self.containers) > 0

def loc_inv_state_factory(
        loc_inv_state: LocInvState = None,
        location: Location = None,
        location_channel_type: ChannelType = None,
        location_coords: Tuple[float, ...] = None,
        containers: Tuple[ContainerState] = None,
        location_container: ContainerState = None,
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
                                id=loc_id)
    _containers = containers if containers is not None else \
        (loc_inv_state.containers if loc_inv_state else None) or tuple()

    _location_container = location_container if location_container else (loc_inv_state.location_container if loc_inv_state else None)

    return LocInvState(
        location=_location,
        containers=_containers,
        location_container=_location_container
    )


if __name__ == "__main__":
    import coopstorage.uom_manifest as uoms
    from pprint import pprint
    test_loc = Location(id='Test', uom_capacities=frozenset([UoMCapacity(x, 999) for x in uoms.manifest]))
    state = LocInvState(
        location=test_loc
    )

    pprint(state.as_dict())