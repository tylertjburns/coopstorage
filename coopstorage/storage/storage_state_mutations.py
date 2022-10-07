from coopstorage.my_dataclasses import Content, Location, StorageState, storage_state_factory, location_prioritizer, Resource, loc_inv_state_factory, UoMCapacity, ContainerState
import coopstorage.storage.loc_inv_state_mutations as lism
import coopstorage.storage.loc_state_mutations as lsm
from coopstorage.logger import logger
from typing import List, Union
from coopstorage.exceptions import *

def add_content(storage_state: StorageState,
                to_add: Union[Content, ContainerState],
                location: Location = None,
                loc_prioritizer: location_prioritizer = None) -> StorageState:
    # ensure concrete location
    if location is None:
        location = storage_state.find_location_for_content(to_add, prioritizer=loc_prioritizer)

    # get new inv state at loc
    if type(to_add) == ContainerState:
        new_loc_inv_state = lism.add_container_to_location(inv_state=storage_state[location], container=to_add)
    elif type(to_add) == Content:
        new_loc_inv_state = lism.add_content_to_location(inv_state=storage_state[location], content=to_add)
    else:
        raise NotImplementedError(f"the object type {type(to_add)} may not be added to storage")

    # get new overall state
    new_storage_state = storage_state_factory(storage_state=storage_state,
                                              updated_locinv_states=[new_loc_inv_state])

    # log
    logger.info(f"{to_add} added to {location} in {storage_state} yielding {new_storage_state}")

    return new_storage_state



def remove_content(
        storage_state: StorageState,
        to_remove: Union[Content, ContainerState],
        location: Location = None,
        loc_prioritizer: location_prioritizer = None) -> StorageState:

    if location is None:
        location = storage_state.find_location_with_content(content=to_remove, prioritizer=loc_prioritizer)

    # get new inv state at loc
    if type(to_remove) == Content:
        new_loc_inv_state = lism.remove_content_from_location(inv_state=storage_state[location], content=to_remove)
    elif type(to_remove) == ContainerState:
        new_loc_inv_state = lism.remove_container_from_location(inv_state=storage_state[location], container=to_remove)
    else:
        raise NotImplementedError(f"Object of type {type(to_remove)} cannot be removed from storage")

    # get new overall state
    new_storage_state = storage_state_factory(storage_state=storage_state,
                                              updated_locinv_states=[new_loc_inv_state])

    # log
    logger.info(f"{to_remove} removed from {location} in {storage_state} yielding {new_storage_state}")

    return new_storage_state

def add_locations(state: StorageState, locations: List[Location]) -> StorageState:
    new_state = storage_state_factory(
        storage_state=state,
        added_locations=locations
    )
    logger.info(f"{locations} added to {state} yielding {new_state}")

    return new_state

def remove_locations(state: StorageState, locations: List[Location]) -> StorageState:
    new_state = storage_state_factory(
        storage_state=state,
        removed_locations=locations
    )

    logger.info(f"{locations} removed from {state} yielding {new_state}")
    return new_state

def adjust_location(state: StorageState,
                    location: Location,
                    added_resources: List[Resource] = None,
                    removed_resources: List[Resource] = None,
                    added_uom_capacities: List[UoMCapacity] = None,
                    removed_uom_capacities: List[UoMCapacity] = None
                    ) -> StorageState:
    new_loc = lsm.adjust_location(location=location,
                                  new_resource_limitations=added_resources,
                                  removed_resource_limitations=removed_resources,
                                  added_uom_capacities=added_uom_capacities,
                                  removed_uom_capacities=removed_uom_capacities
                                  )

    new_loc_inv_state = loc_inv_state_factory(
        loc_inv_state=state.LocInvStateByLocation[new_loc],
        location=new_loc
    )

    new_storage_state = storage_state_factory(
        storage_state=state,
        updated_locinv_states=[new_loc_inv_state]
    )

    return new_storage_state


