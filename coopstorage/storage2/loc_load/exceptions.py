from coopstorage.storage2.loc_load.types import *
from coopstorage.storage2.loc_load.qualifiers import LocationQualifier

class UnknownLocationIdException(Exception):
    def __init__(self, loc_id: UniqueId):
        super().__init__(f"Location {loc_id} not known...")

class UnknownLoadIdException(Exception):
    def __init__(self, lpn: UniqueId):
        super().__init__(f"Load LPN {lpn} not known...")

class NoLocationsMatchFilterCriteriaException(Exception):
    def __init__(self,
                 filter: LocationQualifier,
                 ):
        super().__init__(f"No location found that matches {filter}")