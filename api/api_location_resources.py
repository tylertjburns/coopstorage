from api.constants import *
from flask_restful import Resource, reqparse
import coopstorage.my_dataclasses as md
from coopstorage.storage import Storage
from typing import Tuple


class Api_LocationResources(Resource):
    def __init__(self, inv: Storage):
        self.inv = inv
        super().__init__()

    def _resolve_args(self) -> Tuple[md.Resource, md.Location]:
        parser = reqparse.RequestParser()  # initialize

        # add arguments
        parser.add_argument(LOC_ID_TXT, required=True, location='form')
        parser.add_argument(RESOURCE_TXT, required=True, location='form')

        # parse arguments to dictionary
        args = parser.parse_args()

        # create objs
        loc = md.location_factory(id=args[LOC_ID_TXT])
        resource = md.Resource(name=args[RESOURCE_TXT], type=md.ResourceType.DEFAULT)

        return resource, loc

    def get(self):
        # initialize
        parser = reqparse.RequestParser()

        # add arguments
        parser.add_argument(LOC_ID_TXT, required=True, location='form')

        # parse arguments to dictionary
        args = parser.parse_args()

        # create objs
        loc = self.inv.location_by_id(args[LOC_ID_TXT])

        if loc:
            resource_limitations = loc.resource_limitations
            return {'data': [x.as_dict() for x in resource_limitations]}, 200
        else:
            return {'message': f"no location exists with id: {args[LOC_ID_TXT]}"}, 400

    def post(self):
        resource, loc = self._resolve_args()

        # create objs
        lookup_loc = self.inv.location_by_id(loc.id)

        if not lookup_loc:
            return {'message': f"no location exists with id: {loc.id}"}, 400

        new_loc = self.inv.add_resource_limitations_to_location(location=lookup_loc, resources=[resource])
        return {'data': new_loc.as_dict()}, 200


    def delete(self):
        pass