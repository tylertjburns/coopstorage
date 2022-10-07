from coopstorage.my_dataclasses import Location, LocInvState, Content, loc_inv_state_factory, content_factory, merge_content, ContainerState, container_factory, UnitOfMeasure, location_factory
from coopstorage.exceptions import *
from coopstorage.enums import ChannelType
from coopstorage.storage import cubing as cubing
from coopstorage.storage import containerstate_mutations as csm
from coopstorage.eventDefinition import StorageException
from typing import List
import pprint
from coopstorage.constants import *

def _merge_container_at_location(inv_state: LocInvState, contents: List[Content]) -> LocInvState:
    new_cntnr = csm.add_content_to_container(container=inv_state.location_container, contents=contents)

    # create new state
    new_inv_state = loc_inv_state_factory(
        loc_inv_state=inv_state,
        location_container=new_cntnr
    )
    return new_inv_state

def add_content_to_location(inv_state: LocInvState, content: Content, echo: bool = False) -> LocInvState:
    if inv_state.location.channel_type != ChannelType.MERGED_CONTENT:
        raise StorageException(args=cevents.OnLocationDoesNotSupportAddingContentExceptionEventArgs(
            location=inv_state.location
        ))

    new = _merge_container_at_location(inv_state, [content])

    if echo:
        pprint.pprint(new.as_dict())

    return new

def add_container_to_location(inv_state: LocInvState, container: ContainerState, echo: bool = False) -> LocInvState:
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

def remove_container_from_location(inv_state: LocInvState, container: ContainerState, echo: bool = False) -> LocInvState:
    # verify that location channel allows containers to be removed
    if inv_state.location.channel_type == ChannelType.MERGED_CONTENT:
        raise cevents.StorageException(cevents.OnContainerCannotBeRemovedFromChannelType(
            location=inv_state.location
        ))


    # check if container is in location
    if not container in inv_state.containers:
        raise StorageException(cevents.OnContainerNotFoundException_EventArgs(
            inv_state=inv_state,
            container=container
        ))

    # check if container is in a position to be removed
    if container not in inv_state.ExtractableContainers:
        raise StorageException(cevents.OnContainerNotInExtractablePositionExceptionEventArgs(
            inv_state=inv_state,
            container=container
        ))

    #remove container
    containers = list(inv_state.containers)
    containers.remove(container)
    new_state = loc_inv_state_factory(loc_inv_state=inv_state, containers=tuple(containers))

    if echo:
        pprint.pprint(new_state.as_dict())

    return new_state

def remove_content_from_location(inv_state: LocInvState, content: Content, echo: bool = False) -> LocInvState:
    # verify that location channel is a merged content type
    if inv_state.location.channel_type != ChannelType.MERGED_CONTENT:
        raise cevents.StorageException(cevents.OnContentCannotBeRemovedFromChannelTypeException_EventArgs(
            location=inv_state.location
        ))

    # check if container is in location, and that there is enough content to satisfy
    if inv_state.QtyResourceUoMs[content.resourceUoM] < content.qty:
        raise StorageException(cevents.OnContainerNotFoundException_EventArgs(
            inv_state=inv_state,
            container=None
        ))

    # update container
    container = inv_state.location_container
    new_cntnr = csm.remove_content_from_container(container=container, content=content)
    new_state = loc_inv_state_factory(loc_inv_state=inv_state, location_container=new_cntnr)

    if echo:
        pprint.pprint(new_state.as_dict())

    return new_state

if __name__ == "__main__":
    import coopstorage.uom_manifest as uoms
    from coopstorage.my_dataclasses import UoMCapacity
    import pprint

    test_loc = Location(id='Test', uom_capacities=frozenset([UoMCapacity(x, 999) for x in uoms.manifest]), channel_type=ChannelType.ALL_ACCESSIBLE)
    state = LocInvState(
        location=test_loc
    )

    container_to_add1 = ContainerState(lpn="ABC", uom=uoms.box)
    new_state = add_container_to_location(state, container_to_add1, echo=True)

    container_to_add2 = ContainerState(lpn="123", uom=uoms.box)
    new_state = add_container_to_location(new_state, container_to_add2, echo=True)

    new_state = remove_container_from_location(new_state, container_to_add1, echo=True)
