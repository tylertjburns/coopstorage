import uuid
from coopstorage.my_dataclasses import Location, Content, content_factory, ResourceUoM, StorageState, loc_inv_state_factory
import coopstorage.storage.storage_state_mutations as ssm
from typing import List
import threading

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
        print(self.state.Inventory)

    def add_content(self, content: Content, location: Location = None):
        with self._lock:
           self.state = ssm.add_content(
               storage_state=self.state,
               content=content,
               location=location
           )

    def remove_content(
            self,
            content: Content,
            location: Location = None) -> Content:
        with self._lock:
            self.state = ssm.remove_content(
                storage_state=self.state,
                content=content,
                location=location
            )

        return content


if __name__ == "__main__":
    from coopstorage.my_dataclasses import Resource, ResourceType, UoM, UoMCapacity, location_factory
    import tests.uom_manifest as uoms
    import tests.sku_manifest as skus
    import pprint

    uom_capacities = frozenset([UoMCapacity(uom=uoms.each, capacity=10)])
    locs = [location_factory(uom_capacities=uom_capacities, id=str(ii)) for ii in range(10)]

    inv = Storage(locs)

    for ii in range(4):
        new_cont = content_factory(resource=skus.sku_a, uom=uoms.each, qty=3)
        inv.add_content(new_cont)

    for ii in range(3):
        new_cont = content_factory(resource=skus.sku_b, uom=uoms.each, qty=2)
        inv.add_content(new_cont)

    pprint.pprint(inv)
    rus = [
        ResourceUoM(resource=skus.sku_a, uom=uoms.each),
        ResourceUoM(resource=skus.sku_b, uom=uoms.each),
     ]
    pprint.pprint(inv.state.qty_of_resource_uoms(rus))

    inv.remove_content(Content(ResourceUoM(skus.sku_a, uoms.each), 3))

    pprint.pprint(inv.state.InventoryByResourceUom)