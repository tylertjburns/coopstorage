from flask import Flask
from flask_restful import Resource, Api, reqparse
import ast
from coopstorage.storage import Storage
from coopstorage.my_dataclasses import ResourceUoM, UoMCapacity, location_factory, content_factory, Content, location_generation, Location, resourceUom_factory
import tests.uom_manifest as uoms
from coopstorage.api.api_locations import Api_Locations
from coopstorage.api.api_inventory import Api_Inventory
from coopstorage.api.api_resourceUomManifest import Api_ResourceUoMManifest


app = Flask(__name__)
api = Api(app)

locs = location_generation(loc_template_quantities=
{
    Location(uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=10)])): 1,
    Location(uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=4)])): 1
})

inv = Storage(locs)

api.add_resource(Api_Locations, '/locations', resource_class_kwargs={'inv': inv})
api.add_resource(Api_Inventory, '/inventory', resource_class_kwargs={'inv': inv})
api.add_resource(Api_ResourceUoMManifest, '/resourceuoms', resource_class_kwargs={'inv': inv})

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True)

