from api.constants import *
from flask_restful import Resource, reqparse
import coopstorage.my_dataclasses as md
from coopstorage.storage import Storage
from typing import Tuple


class Api_LocationUoMCapacity(Resource):
    def __init__(self, inv: Storage):
        self.inv = inv
        super().__init__()

    def _resolve_args(self) -> Tuple[md.UoMCapacity, md.Location]:
        parser = reqparse.RequestParser()  # initialize

        # add arguments
        parser.add_argument(LOC_ID_TXT, required=True, location='form')
        parser.add_argument(UOM_TXT, required=True, location='form')
        parser.add_argument(QTY_TXT, required=True, location='form')

        # parse arguments to dictionary
        args = parser.parse_args()

        # create objs
        loc = md.location_factory(id=args[LOC_ID_TXT])
        uom_cap = md.UoMCapacity(uom=md.UnitOfMeasure(args[UOM_TXT]), capacity=float(args[QTY_TXT]))

        return uom_cap, loc

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
            uom_cap = loc.uom_capacities
            return {DATA_HEADER: [x.as_dict() for x in uom_cap]}, 200
        else:
            return {ERROR_HEADER: f"no location exists with id: {args[LOC_ID_TXT]}"}, 400

    def post(self):
        uom_cap, loc = self._resolve_args()

        # create objs
        lookup_loc = self.inv.location_by_id(loc.id)

        if not lookup_loc:
            return {ERROR_HEADER: f"no location exists with id: {loc.id}"}, 400

        try:
            new_loc = self.inv.adjust_location(location=lookup_loc, added_uom_capacities=[uom_cap])
            return {DATA_HEADER: new_loc.as_dict()}, 200
        except Exception as e:
            return {ERROR_HEADER: str(e)}, 400

    def delete(self):
        uom_cap, loc = self._resolve_args()

        # create objs
        lookup_loc = self.inv.location_by_id(loc.id)

        if not lookup_loc:
            return {ERROR_HEADER: f"no location exists with id: {loc.id}"}, 400

        try:
            new_loc = self.inv.adjust_location(location=lookup_loc, removed_uom_capacities=[uom_cap])
            return {DATA_HEADER: new_loc.as_dict()}, 200
        except Exception as e:
            return {ERROR_HEADER: str(e)}, 400