from cooptools.protocols import UniqueIdentifier
from coopstorage.storage.loc_load.qualifiers import LocationQualifier

class UnknownLocationIdException(Exception):
    def __init__(self, loc_id: UniqueIdentifier):
        super().__init__(f"Location {loc_id} not known...")

class UnknownLoadIdException(Exception):
    def __init__(self, lpn: UniqueIdentifier):
        super().__init__(f"Load LPN {lpn} not known...")

class NoLocationsMatchFilterCriteriaException(Exception):
    def __init__(self,
                 filter: LocationQualifier,
                 ):
        super().__init__(f"No location found that matches {filter}")

class UnexpectedContainerCountException(Exception):
    def __init__(self, loc_id: UniqueIdentifier, expected: int, actual: int):
        super().__init__(f"Location {loc_id} has {actual} containers, expected {expected}")

class UnblockDeadlockError(Exception):
    def __init__(self, target_id, blocker_id, in_flight: set):
        super().__init__(
            f"Deadlock detected while unblocking: container {blocker_id} blocks {target_id} "
            f"but is already in the active unblock chain {in_flight}"
        )