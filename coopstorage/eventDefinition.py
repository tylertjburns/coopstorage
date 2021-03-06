import logging

from pubsub import pub
from enum import Enum, auto
import datetime
from dataclasses import dataclass, field
from coopstorage.my_dataclasses import Content, Location, LocInvState, UoM
from typing import Dict, Optional, List, Any

logger = logging.getLogger('coopstorage.events')

class ProductionEventType(Enum):
    EXCEPTION_LOCATION_NOT_IN_STORAGE = auto()
    EXCEPTION_NO_LOCATION_FOUND = auto()
    EXCEPTION_NO_LOCATION_WITH_CAPACITY_FOUND = auto()
    EXCEPTION_CONTENT_DOESNT_MATCH_LOCATION = auto()
    EXCEPTION_CONTENT_DOESNT_MATCH_LOCATION_ACTIVE_DESIGNATION = auto()
    EXCEPTION_NO_ROOM_AT_LOCATION = auto()
    EXCEPTION_MISSING_CONTENT = auto()
    EXCEPTION_NO_LOCATION_TO_REMOVE_CONTENT = auto()

def raise_event(event: ProductionEventType,
                log_lvl=logging.INFO,
                **kwargs):
    args = kwargs.get('args', None)
    logger.log(level=log_lvl, msg=f"raise event: {event.name} with args: {args}")
    pub.sendMessage(event.name, **kwargs)

#region EventArgsBase
@dataclass(frozen=True)
class EventArgsBase:
    date_stamp: datetime.datetime = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'date_stamp', datetime.datetime.now())

@dataclass(frozen=True)
class LocationEventArgsBase(EventArgsBase):
    location: Location

@dataclass(frozen=True)
class ContentEventArgsBase(EventArgsBase):
    content: Content

@dataclass(frozen=True)
class StorageEventArgsBase(EventArgsBase):
    storage_state: Any

@dataclass(frozen=True)
class LocInvEventArgsBase(EventArgsBase):
    loc_inv: LocInvState


#region ExceptionEventArgs
@dataclass(frozen=True)
class OnContentDoesntMatchLocationExceptionEventArgs(LocationEventArgsBase, ContentEventArgsBase):
    ...

@dataclass(frozen=True)
class OnNoRoomAtLocationExceptionEventArgs(LocInvEventArgsBase):
    ...

@dataclass(frozen=True)
class OnMissingContentExceptionEventArgs(LocInvEventArgsBase):
    ...


@dataclass(frozen=True)
class OnLocationNotInStorageExceptionEventArgs(StorageEventArgsBase):
    ...

@dataclass(frozen=True)
class OnNoLocationFoundExceptionEventArgs(StorageEventArgsBase):
    ...

@dataclass(frozen=True)
class OnNoLocationWithCapacityExceptionEventArgs(StorageEventArgsBase, ContentEventArgsBase):
    resource_uom_space: float
    loc_uom_space_avail: Dict[Location, float]
    loc_states: List[LocInvState]

@dataclass(frozen=True)
class OnContentDoesntMatchLocationActiveDesignationExceptionEventArgs(LocInvEventArgsBase, ContentEventArgsBase):
    ...

@dataclass(frozen=True)
class OnNoLocationToRemoveContentExceptionEventArgs(StorageEventArgsBase, ContentEventArgsBase):
    ...
#endregion

#region RaiseEvents
def raise_event_LocationNotInStorageException(args: OnLocationNotInStorageExceptionEventArgs):
    raise_event(ProductionEventType.EXCEPTION_LOCATION_NOT_IN_STORAGE, log_lvl=logging.ERROR, args=args)

def raise_event_NoLocationFoundException(args: OnNoLocationFoundExceptionEventArgs):
    raise_event(ProductionEventType.EXCEPTION_NO_LOCATION_FOUND, log_lvl=logging.ERROR, args=args)

def raise_event_NoLocationWithCapacityException(args: OnNoLocationWithCapacityExceptionEventArgs):
    raise_event(ProductionEventType.EXCEPTION_NO_LOCATION_WITH_CAPACITY_FOUND, log_lvl=logging.ERROR, args=args)

def raise_event_ContentDoesntMatchLocationException(args: OnContentDoesntMatchLocationExceptionEventArgs):
    raise_event(ProductionEventType.EXCEPTION_CONTENT_DOESNT_MATCH_LOCATION, log_lvl=logging.ERROR, args=args)

def raise_event_ContentDoesntMatchLocationDesignationException(args: OnContentDoesntMatchLocationActiveDesignationExceptionEventArgs):
    raise_event(ProductionEventType.EXCEPTION_CONTENT_DOESNT_MATCH_LOCATION_ACTIVE_DESIGNATION, log_lvl=logging.ERROR, args=args)

def raise_event_NoRoomAtLocationException(args: OnNoRoomAtLocationExceptionEventArgs):
    raise_event(ProductionEventType.EXCEPTION_NO_ROOM_AT_LOCATION, log_lvl=logging.ERROR, args=args)

def raise_event_MissingContentException(args: OnMissingContentExceptionEventArgs):
    raise_event(ProductionEventType.EXCEPTION_MISSING_CONTENT, log_lvl=logging.ERROR, args=args)

def raise_event_NoLocationToRemoveContentException(args: OnNoLocationToRemoveContentExceptionEventArgs):
    raise_event(ProductionEventType.EXCEPTION_NO_LOCATION_TO_REMOVE_CONTENT, log_lvl=logging.ERROR, args=args)

#endregion

if __name__ == "__main__":
    pass