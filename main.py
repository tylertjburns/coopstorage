from coopstorage.my_dataclasses import ResourceUoM, UoMCapacity, location_factory, content_factory, Content
from coopstorage.storage import Storage
import tests.uom_manifest as uoms
import tests.sku_manifest as skus
import pprint


def main():

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

if __name__ == "__main__":
    main()