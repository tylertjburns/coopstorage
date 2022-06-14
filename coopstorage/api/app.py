from flask import Flask
from flask_restful import Resource, Api, reqparse
import ast
from coopstorage.storage import Storage
from coopstorage.my_dataclasses import ResourceUoM, UoMCapacity, location_factory, content_factory, Content, location_generation, Location, resourceUom_factory
import tests.uom_manifest as uoms
from dataclasses import asdict
from coopstorage.exceptions import *
from typing import Tuple
from functools import partial
import coopstorage.location_search_prioritizers as lprios

app = Flask(__name__)
api = Api(app)

locs = location_generation(loc_template_quantities=
{
    Location(uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=10)])): 10,
    Location(uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=4)])): 5
})

inv = Storage(locs)

_resource = 'resource'
_resource_description = 'resource_description'
_uom = 'uom'
_qty = 'qty'
_loc_id = 'loc_id'


class Api_ResourceUoMManifest(Resource):
    def _resource_uom_manifest(self):
        return {'data': [x.as_dict() for x in inv.state.ResourceUoMManifest]}

    def get(self):
        return self._resource_uom_manifest(), 200

    def post(self):
        parser = reqparse.RequestParser()  # initialize

        # add arguments
        parser.add_argument(_resource, required=True, location='form')
        parser.add_argument(_uom, required=True, location='form')
        parser.add_argument(_resource_description, required=False, location='form')

        # parse arguments to dictionary
        args = parser.parse_args()

        resource_uom = resourceUom_factory(resource_name=args[_resource],
                                           uom_name=args[_uom],
                                           resource_description=args[_resource_description])

        if resource_uom in inv.resource_uom_manifest:
            return {'message': f'{resource_uom} already in manifest'}, 400
        else:
            inv.add_resource_uoms_to_manifest([resource_uom])
            return self._resource_uom_manifest(), 200

class Api_Inventory(Resource):
    loc_prio_smallest_first_each_uom = partial(lprios.by_space_available, uom=uoms.each, smallest_first=True)
    loc_prio_smallest_content_present = partial(lprios.by_content_present, smallest_first=True)

    def _resolve_args(self) -> Tuple[Content, Location]:
        parser = reqparse.RequestParser()  # initialize

        # add arguments
        parser.add_argument(_resource, required=True, location='form')
        parser.add_argument(_uom, required=True, location='form')
        parser.add_argument(_qty, required=True, location='form')
        parser.add_argument(_loc_id, required=False, location='form')

        # parse arguments to dictionary
        args = parser.parse_args()

        # resolve uom
        entered_resource_uom = resourceUom_factory(resource_name=args[_resource],
                                                   uom_name=args[_uom])

        # create content
        content = content_factory(resource_uom=entered_resource_uom,
                                  qty=int(args[_qty]))

        # create location
        loc = inv.location_by_id(args[_loc_id])

        return content, loc

    def get(self):
        return {'data': inv.state.as_dict()}, 200

    def post(self):
        content, loc = self._resolve_args()

        # add content
        try:
            inv.add_content(content=content,
                            location=loc)

            return inv.state.as_dict(), 200
        except Exception as e:
            return {'message': str(e)}, 400

    def delete(self):
        content, loc = self._resolve_args()

        # add content
        try:
            inv.remove_content(content=content,
                                location=loc,
                               loc_prioritizer=lambda x: self.loc_prio_smallest_content_present(x, ru=content.resourceUoM))

            return inv.state.as_dict(), 200
        except Exception as e:
            return {'message': str(e)}, 400

class Flask_Locations(Resource):
    def get(self):
        data = [x.as_dict() for x in inv.state.Locations]
        return {'data': data}

api.add_resource(Flask_Locations, '/locations')
api.add_resource(Api_Inventory, '/inventory')
api.add_resource(Api_ResourceUoMManifest, '/resourceuoms')

if __name__ == "__main__":
    app.run(debug=True)

