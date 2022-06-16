from coopstorage.my_dataclasses import Content, Location, StorageState, storage_state_factory, location_prioritizer, Resource, loc_inv_state_factory
import coopstorage.storage.loc_inv_state_mutations as lism
import coopstorage.storage.loc_state_mutations as lsm
from coopstorage.logger import logger
from typing import List
from coopstorage.exceptions import *

def add_content(storage_state: StorageState,
                content: Content,
                location: Location = None,
                loc_prioritizer: location_prioritizer = None) -> StorageState:
    # ensure concrete location
    if location is None:
        location = storage_state.find_location_for_content(content, prioritizer=loc_prioritizer)

    # get new inv state at loc
    new_loc_inv_state = lism.add_content_to_loc(inv_state=storage_state[location], content=content)

    # get new overall state
    new_storage_state = storage_state_factory(storage_state=storage_state,
                                              updated_locinv_states=[new_loc_inv_state])

    # log
    logger.info(f"{content} added to {location} in {storage_state} yielding {new_storage_state}")

    return new_storage_state

def remove_content(
        storage_state: StorageState,
        content: Content,
        location: Location = None,
        loc_prioritizer: location_prioritizer = None) -> StorageState:

    if location is None:
        location = storage_state.find_location_with_content(content=content, prioritizer=loc_prioritizer)

    # get new inv state at loc
    new_loc_inv_state = lism.remove_content_from_location(inv_state=storage_state[location], content=content)

    # get new overall state
    new_storage_state = storage_state_factory(storage_state=storage_state,
                                              updated_locinv_states=[new_loc_inv_state])

    # log
    logger.info(f"{content} removed from {location} in {storage_state} yielding {new_storage_state}")

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

def add_resource_constraints_to_location(state: StorageState, location: Location, resources: List[Resource]) -> StorageState:
    new_loc = lsm.add_resource_limitations(location=location, new_resource_limitations=resources)
    new_loc_inv_state = loc_inv_state_factory(
        loc_inv_state=state.LocInvStateByLocation[new_loc],
        location=new_loc
    )

    new_storage_state = storage_state_factory(
        storage_state=state,
        updated_locinv_states=[new_loc_inv_state]
    )

    return new_storage_state
