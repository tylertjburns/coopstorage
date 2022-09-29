import time

from coopstorage import Storage, Location, UoMCapacity, uom_manifest as uoms, location_generation, content_factory, ResourceUoM, Content
import coopstorage.location_search_prioritizers as lprios
import tests.sku_manifest as skus
from functools import partial
import logging
import random as rnd

loc_prio_smallest_first_each_uom = partial(lprios.by_space_available, uom=uoms.each, smallest_first=True)
loc_prio_smallest_content_present = partial(lprios.by_content_present, smallest_first=True)

def setup_storage() -> Storage:
    logging.basicConfig(level=logging.DEBUG)

    locs = location_generation(loc_template_quantities=
    {
        Location(uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=10)])): 10,
        Location(uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=4)])): 5
    })

    inv = Storage(locs)

    inv.print()

    return Storage(locations=locs)

def run_long():
    storage = setup_storage()


    while True:
        time.sleep(.1)

        try:
            sku = rnd.choice(skus.manifest)
            qty = rnd.randint(0, 100)
            new_cont = content_factory(resource=sku, uom=uoms.each, qty=qty)
            storage.add_content(new_cont, loc_prioritizer=loc_prio_smallest_first_each_uom)
        except Exception as e:
            print(e)

        try:
            sku = rnd.choice(skus.manifest)
            qty = rnd.randint(0, 100)
            ru_to_remove = ResourceUoM(sku, uoms.each)
            storage.remove_content(Content(ru_to_remove, qty),
                               loc_prioritizer=lambda x: loc_prio_smallest_content_present(x, ru=ru_to_remove))
        except Exception as e:
            print(e)

if __name__ == "__main__":
    run_long()