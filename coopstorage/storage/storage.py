import uuid
from coopstorage.my_dataclasses import Location, Content, content_factory, ResourceUoM, StorageState, loc_inv_state_factory, location_prioritizer
import coopstorage.storage.storage_state_mutations as ssm
from typing import List
import threading
import pprint

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

