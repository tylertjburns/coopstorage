from api.old.constants import *
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
            return {DATA_HEADER: [x.as_dict() for x in resource_limitations]}, 200
        else:
            return {ERROR_HEADER: f"no location exists with id: {args[LOC_ID_TXT]}"}, 400

    def post(self):
        resource, loc = self._resolve_args()

        # create objs
        lookup_loc = self.inv.location_by_id(loc.id)

        if not lookup_loc:
            return {ERROR_HEADER: f"no location exists with id: {loc.id}"}, 400

        try:
            new_loc = self.inv.adjust_location(location=lookup_loc, added_resources=[resource])
            return {DATA_HEADER: new_loc.as_dict_payload()}, 200
        except Exception as e:
            return {ERROR_HEADER: str(e)}, 400

    def delete(self):
        resource, loc = self._resolve_args()

        # create objs
        lookup_loc = self.inv.location_by_id(loc.id)

        if not lookup_loc:
            return {ERROR_HEADER: f"no location exists with id: {loc.id}"}, 400

        try:
            new_loc = self.inv.adjust_location(location=lookup_loc, removed_resources=[resource])
            return {DATA_HEADER: new_loc.as_dict_payload()}, 200
        except Exception as e:
            return {ERROR_HEADER: str(e)}, 400