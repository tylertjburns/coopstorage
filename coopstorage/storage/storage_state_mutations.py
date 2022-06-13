from coopstorage.exceptions import *
from coopstorage.my_dataclasses import Content, Location, StorageState, storage_state_factory
import coopstorage.storage.loc_inv_state_mutations as lism

def add_content(storage_state: StorageState, content: Content, location: Location = None) -> StorageState:
    # ensure concrete location
    if location is None:
        location = storage_state.find_open_location(content)

    # get new inv state at loc
    new_loc_inv_state = lism.add_content_to_loc(inv_state=storage_state[location], content=content)

    # get new overall state
    new_storage_state = storage_state_factory(storage_state=storage_state,
                                              updated_loc_states=[new_loc_inv_state])

    return new_storage_state

def remove_content(
        storage_state: StorageState,
        content: Content,
        location: Location = None) -> StorageState:

    if location is None:
        locations_that_satisfy = storage_state.location_match(resource_uoms=[content.resourceUoM], required_uom_types=[content.uom])
        location = next(iter([loc for loc in locations_that_satisfy
                              if storage_state.qty_resource_uom_at_location(loc, resource_uom=content.resourceUoM) >= content.qty])
                        , None)
    else:
        # TODO: RESOLVE bad location
        raise NotImplementedError()

    # handle no location found
    if location is None:
        raise NoLocationToRemoveContentException(content=content, storage_state=storage_state)

    # get new inv state at loc
    new_loc_inv_state = lism.remove_content_from_location(inv_state=storage_state[location], content=content)

    # get new overall state
    new_storage_state = storage_state_factory(storage_state=storage_state,
                                              updated_loc_states=[new_loc_inv_state])

    return new_storage_state




