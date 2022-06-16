from api.constants import *
from flask_restful import Resource, reqparse
from coopstorage.my_dataclasses import content_factory, Content, Location, resourceUom_factory
import tests.uom_manifest as uoms
from typing import Tuple
from functools import partial
import coopstorage.location_search_prioritizers as lprios
from coopstorage.storage import Storage

class Api_Inventory(Resource):
    loc_prio_smallest_first_each_uom = partial(lprios.by_space_available, uom=uoms.each, smallest_first=True)
    loc_prio_smallest_content_present = partial(lprios.by_content_present, smallest_first=True)

    def __init__(self, inv: Storage):
        self.inv = inv
        super().__init__()

    def _resolve_args(self) -> Tuple[Content, Location]:
        parser = reqparse.RequestParser()  # initialize

        # add arguments
        parser.add_argument(RESOURCE_TXT, required=True, location='form')
        parser.add_argument(UOM_TXT, required=True, location='form')
        parser.add_argument(QTY_TXT, required=True, location='form')
        parser.add_argument(LOC_ID_TXT, required=False, location='form')

        # parse arguments to dictionary
        args = parser.parse_args()

        # resolve uom
        entered_resource_uom = resourceUom_factory(resource_name=args[RESOURCE_TXT],
                                                   uom_name=args[UOM_TXT])

        # create content
        content = content_factory(resource_uom=entered_resource_uom,
                                  qty=int(args[QTY_TXT]))

        # create location
        loc = self.inv.location_by_id(args[LOC_ID_TXT])

        return content, loc

    def get(self):
        return {'data': self.inv.state.as_dict()}, 200

    def post(self):
        content, loc = self._resolve_args()

        # add content
        try:
            self.inv.add_content(content=content,
                            location=loc)

            return self.inv.state.as_dict(), 200
        except Exception as e:
            return {'message': str(e)}, 400

    def delete(self):
        content, loc = self._resolve_args()

        # add content
        try:
            self.inv.remove_content(content=content,
                                location=loc,
                               loc_prioritizer=lambda x: self.loc_prio_smallest_content_present(x, ru=content.resourceUoM))

            return self.inv.state.as_dict(), 200
        except Exception as e:
            return {'message': str(e)}, 400