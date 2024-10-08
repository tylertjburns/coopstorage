from flask import Flask
from flask_restful import Api
from coopstorage.storage import Storage
from coopstorage.my_dataclasses import UoMCapacity, location_generation, Location
import coopstorage.uom_manifest as uoms
from api.old.api_locations import Api_Locations
from api.old.api_inventory import Api_Inventory
from api.old.api_resourceUomManifest import Api_ResourceUoMManifest
from api.old.api_location_resources import Api_LocationResources
from api.old.api_location_uom_capacity import Api_LocationUoMCapacity

def start_api(port: int = 5000):
    app = Flask(__name__)
    api = Api(app)

    locs = location_generation(loc_template_quantities=
    {
        Location(uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=10)])): 1,
        Location(uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=4)])): 1
    })

    inv = Storage(locs)

    api.add_resource(Api_Locations, '/locations', resource_class_kwargs={'inv': inv})
    api.add_resource(Api_LocationResources, '/locations/resourcelimitations', resource_class_kwargs={'inv': inv})
    api.add_resource(Api_Inventory, '/inventory', resource_class_kwargs={'inv': inv})
    api.add_resource(Api_ResourceUoMManifest, '/resourceuoms', resource_class_kwargs={'inv': inv})
    api.add_resource(Api_LocationUoMCapacity, '/locations/uomcapacities', resource_class_kwargs={'inv': inv})

    app.run(debug=True, port=port)

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)
    start_api()


