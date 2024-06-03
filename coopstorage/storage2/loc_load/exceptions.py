from coopstorage.storage2.loc_load.types import *

class UnknownStorerIdException(Exception):
    def __init__(self, loc_id: UniqueId):
        super().__init__(f"Location {loc_id} not known...")

class UnknownLoadIdException(Exception):
    def __init__(self, lpn: UniqueId):
        super().__init__(f"Load LPN {lpn} not known...")