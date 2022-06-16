import uuid
from coopstorage.my_dataclasses import Location, Content, content_factory, Resource, StorageState, loc_inv_state_factory, location_prioritizer
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
        pprint.pprint(self.state.Inventory)

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
               content=content,
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
                content=content,
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

    def add_resource_limitations_to_location(self, location: Location, resources: List[Resource]) -> Location:
        with self._lock:
            self.state=ssm.add_resource_constraints_to_location(
                state=self.state,
                location=location,
                resources=resources
            )

            return self.location_by_id(location.id)

