from coopstorage.my_dataclasses import Content, Location, StorageState, storage_state_factory, location_prioritizer
import coopstorage.storage.loc_inv_state_mutations as lism
from coopstorage.logger import logger

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
                                              updated_loc_states=[new_loc_inv_state])

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
                                              updated_loc_states=[new_loc_inv_state])

    # log
    logger.info(f"{content} removed from {location} in {storage_state} yielding {new_storage_state}")

    return new_storage_state




