from coopstorage.my_dataclasses import ResourceUoM, UoMCapacity, location_factory, content_factory, Content, location_generation, Location
from coopstorage.storage import Storage
import tests.uom_manifest as uoms
import tests.sku_manifest as skus
import pprint
import coopstorage.location_search_prioritizers as lprios
from functools import partial
import logging

def main():
    logging.basicConfig(level=logging.DEBUG)

    locs = location_generation(loc_template_quantities=
    {
        Location(uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=10)])): 10,
        Location(uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=4)])): 5
    })

    inv = Storage(locs)

    inv.print()

    loc_prio_smallest_first_each_uom = partial(lprios.by_space_available, uom=uoms.each, smallest_first=True)
    loc_prio_smallest_content_present = partial(lprios.by_content_present, smallest_first=True)


    new_cont = content_factory(resource=skus.sku_a, uom=uoms.each, qty=3)
    inv.add_content(new_cont, loc_prioritizer=loc_prio_smallest_first_each_uom)

    for ii in range(4):
        new_cont = content_factory(resource=skus.sku_a, uom=uoms.each, qty=4)
        inv.add_content(new_cont, loc_prioritizer=loc_prio_smallest_first_each_uom)

    for ii in range(3):
        new_cont = content_factory(resource=skus.sku_b, uom=uoms.each, qty=2)
        inv.add_content(new_cont, loc_prioritizer=loc_prio_smallest_first_each_uom)

    pprint.pprint(inv)
    rus = [
        ResourceUoM(resource=skus.sku_a, uom=uoms.each),
        ResourceUoM(resource=skus.sku_b, uom=uoms.each),
     ]
    pprint.pprint(inv.state.qty_of_resource_uoms(rus))

    ru_to_remove = ResourceUoM(skus.sku_a, uoms.each)
    inv.remove_content(Content(ru_to_remove, 3),
                       loc_prioritizer=lambda x: loc_prio_smallest_content_present(x, ru=ru_to_remove))

    inv.print()
    pprint.pprint(inv.state.InventoryByResourceUom)

if __name__ == "__main__":
    main()