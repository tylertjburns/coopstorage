from flask_restful import Resource, Api, reqparse
from coopstorage.storage import Storage
from api.constants import *

class Api_ResourceUoMManifest(Resource):

    def __init__(self, inv: Storage):
        self.inv = inv
        super().__init__()

    def _resource_uom_manifest(self):
        return {DATA_HEADER: [x.as_dict() for x in self.inv.state.ResourceUoMManifest]}

    def get(self):
        return self._resource_uom_manifest(), 200