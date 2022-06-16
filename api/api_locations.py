from api.constants import *
from flask_restful import Resource, reqparse
from coopstorage.my_dataclasses import Location, location_factory
from coopstorage.storage import Storage


class Api_Locations(Resource):
    def __init__(self, inv: Storage):
        self.inv = inv
        super().__init__()

    def _resolve_args(self, id_required: bool = False) -> Location:
        parser = reqparse.RequestParser()  # initialize

        # add arguments
        parser.add_argument(LOC_ID_TXT, required=id_required, location='form')

        # parse arguments to dictionary
        args = parser.parse_args()

        # create loc
        loc = location_factory(id=args[LOC_ID_TXT])

        return loc

    def _location_manifest(self):
        return {'data': [x.as_dict() for x in self.inv.state.Locations]}

    def get(self):
        return self._location_manifest(), 200

    def post(self):
        loc = self._resolve_args()

        self.inv.add_locations([loc])
        return {'data': loc.as_dict()}, 200

    def delete(self):
        loc = self._resolve_args(id_required=True)

        try:
            self.inv.remove_locations([loc])
            return self._location_manifest(), 200
        except Exception as e:
            return {'message': str(e)}, 400