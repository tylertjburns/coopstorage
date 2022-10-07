import uuid
from coopstorage.my_dataclasses import Location, Content, content_factory, Resource, StorageState, loc_inv_state_factory, location_prioritizer, UoMCapacity
import coopstorage.storage.storage_state_mutations as ssm
from typing import List, Union
import threading
import pprint
from coopstorage.exceptions import *
from coopstorage.resolvers import try_resolve_guid

class Storage:

    def __init__(self,
                 locations: List[Location],
                 id: str = None):

        self._id = id or uuid.uuid4()
        self.state = StorageState(
            loc_states=frozenset([loc_inv_state_factory(location=x) for x in locations])
        )
        self._lock = threading.RLock()

    def __str__(self):
        return f"id: {self._id}, Locs: {len(self.state.Inventory)}, occupied: {len(self.state.OccupiedLocs)}, empty: {len(self.state.EmptyLocs)}"

    def print(self):
        self.state.print()

    def add_content(self,
                    content: Content,
                    location: Location = None,
                    loc_prioritizer: location_prioritizer = None):
        with self._lock:
            lookup_resource_uom = next(iter(x for x in self.state.ResourceUoMManifest if x == content.resourceUoM), None)

            content = content_factory(content=content, resource_uom=lookup_resource_uom) if lookup_resource_uom else \
                content

            self.state = ssm.add_content(
               storage_state=self.state,
               to_add=content,
               location=location,
               loc_prioritizer=loc_prioritizer
            )

    def remove_content(
            self,
            content: Content,
            location: Location = None,
            loc_prioritizer: location_prioritizer=None) -> Content:
        with self._lock:
            self.state = ssm.remove_content(
                storage_state=self.state,
                to_remove=content,
                location=location,
                loc_prioritizer=loc_prioritizer
            )

        return content

    def location_by_id(self, id: Union[str, uuid.UUID]) -> Location:
        return next(iter([x for x in self.state.Locations if x.id == try_resolve_guid(id)]), None)

    def add_locations(self, locations: List[Location]):
        with self._lock:
            self.state=ssm.add_locations(state=self.state, locations=locations)

    def remove_locations(self, locations: List[Location]):
        with self._lock:
            self.state=ssm.remove_locations(state=self.state, locations=locations)

    def adjust_location(self,
                        location: Location,
                        added_resources: List[Resource]=None,
                        removed_resources: List[Resource]=None,
                        added_uom_capacities: List[UoMCapacity]=None,
                        removed_uom_capacities: List[UoMCapacity]=None
                        ) -> Location:
        with self._lock:
            self.state=ssm.adjust_location(
                state=self.state,
                location=location,
                added_resources=added_resources,
                removed_resources=removed_resources,
                added_uom_capacities=added_uom_capacities,
                removed_uom_capacities=removed_uom_capacities
            )

            return self.location_by_id(location.id)

