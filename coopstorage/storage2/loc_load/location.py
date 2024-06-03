import coopstorage.storage2.loc_load.dcs as dcs
from coopstorage.storage2.loc_load.types import UniqueId
from coopstorage.storage2.loc_load.channel_processors import IChannelProcessor
from typing import List, Optional, Dict

class Location:
    def __init__(self,
                 id: UniqueId,
                 location_meta: dcs.LocationMeta,
                 channel_processor: IChannelProcessor):

        self._id = id
        self._meta = location_meta
        self._channel_processor = channel_processor
        self._loads = [None for _ in range(self._meta.capacity)]


    @property
    def Capacity(self) -> int:
        return self._meta.capacity

    @property
    def AvailableCapacity(self) -> int:
        return self._meta.capacity - len(self.LoadPositions)

    @property
    def LoadPositions(self) -> Dict[int, dcs.Load]:
        return {ii: x for ii, x in enumerate(self._loads)}



    def add_load(self, load: dcs.Load, echo: bool = False):




        if inv_state.location.channel_type == ChannelType.MERGED_CONTENT:
            return _merge_container_at_location(inv_state=inv_state, contents=list(container.contents))

        uom_types_to_store = [container.UoM]

        # verify that the uom types match the location uom capacities of the location
        cubing.check_raise_uom_capacity_match(check_uoms=uom_types_to_store, uom_capacities=list(inv_state.location.uom_capacities))

        # verify capacity
        qty_at_loc = inv_state.QtyContainerUoMs.get(container.UoM, 0)
        cubing.check_raise_uom_qty_doesnt_fit(
            uom=container.uom,
            capacity=inv_state.location.UoMCapacities[container.UoM],
            current=qty_at_loc,
            qty=1
        )

        # add container and merge at location
        new_containers = list(inv_state.containers)
        new_containers.append(container)

        # create new state
        new_state = loc_inv_state_factory(
            loc_inv_state=inv_state,
            containers=tuple(new_containers),
        )

        if echo:
            pprint.pprint(new_state.as_dict())

        return new_state
