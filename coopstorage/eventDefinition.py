import logging

from pubsub import pub
from enum import Enum, auto
import datetime
from dataclasses import dataclass, field
from coopstorage.my_dataclasses import Content, Location, LocInvState, UnitOfMeasure, UoMCapacity, ResourceUoM, ContainerState
from typing import Dict, Optional, List, Any

logger = logging.getLogger('coopstorage.events')

class StorageEventType(Enum):
    EXCEPTION_LOCATION_NOT_IN_STORAGE = auto()
    EXCEPTION_NO_LOCATION_FOUND = auto()
    EXCEPTION_NO_LOCATION_WITH_CAPACITY_FOUND = auto()
    EXCEPTION_UOMS_DONT_MATCH_UOM_CAPACITY_DEFINITION = auto()
    EXCEPTION_CONTENT_DOESNT_MATCH_LOCATION_ACTIVE_DESIGNATION = auto()
    EXCEPTION_QTY_OF_UOM_DOESNT_FIT_AT_DESTINATION = auto()
    EXCEPTION_MISSING_CONTENT = auto()
    EXCEPTION_MISSING_UOMS = auto()
    EXCEPTION_CONTAINER_NOT_IN_EXTRACTABLE_POSITION = auto()
    EXCEPTION_NO_LOCATION_TO_REMOVE_CONTENT = auto()
    EXCEPTION_LOCATION_DOES_NOT_SUPPORT_ADDING_CONTENT = auto()
    EXCEPTION_CONTAINER_CANNOT_BE_REMOVED_FROM_CHANNEL_TYPE = auto()
    EXCEPTION_CONTENT_CANNOT_BE_REMOVED_FROM_CHANNEL_TYPE = auto()
    EXCEPTION_CONTAINER_NOT_FOUND = auto()

def raise_event(event: StorageEventType,
                log_lvl=logging.INFO,
                **kwargs):
    args = kwargs.get('args', None)
    logger.log(level=log_lvl, msg=f"raise event: {event.name} with args: {args.__dict__}")
    pub.sendMessage(event.name, **kwargs)

#region EventArgsBase
@dataclass(frozen=True)
class EventArgsBase:
    date_stamp: datetime.datetime = field(init=False)
    event_type: StorageEventType

    def __post_init__(self):
        object.__setattr__(self, 'date_stamp', datetime.datetime.now())

    def __str__(self):
        return f"{type(self).__name__}"


#region ExceptionEventArgs
@dataclass(frozen=True)
class OnUoMsDontMatchUoMCapacityDefinitionExceptionEventArgs(EventArgsBase):
    uoms: List[UnitOfMeasure]
    uom_capacities: List[UoMCapacity]
    event_type: StorageEventType=field(init=False, default=StorageEventType.EXCEPTION_UOMS_DONT_MATCH_UOM_CAPACITY_DEFINITION)

@dataclass(frozen=True)
class OnQtyUoMDoesntFitAtDestinationExceptionEventArgs(EventArgsBase):
    uom: UnitOfMeasure
    new: float
    current: float
    capacity: float
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_QTY_OF_UOM_DOESNT_FIT_AT_DESTINATION)

@dataclass(frozen=True)
class OnNotEnoughUoMsException_EventArgs(EventArgsBase):
    uom: UnitOfMeasure
    qty: float
    current: Dict[UnitOfMeasure, float]
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_MISSING_UOMS)


@dataclass(frozen=True)
class OnNotEnoughContentException_EventArgs(EventArgsBase):
    requested_content: Content
    current_content: List[Content]
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_MISSING_CONTENT)

@dataclass(frozen=True)
class OnLocationNotInStorageExceptionEventArgs(EventArgsBase):
    loc_inv: LocInvState
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_LOCATION_NOT_IN_STORAGE)

@dataclass(frozen=True)
class OnNoLocationFoundExceptionEventArgs(EventArgsBase):
    storage_state: Any
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_NO_LOCATION_FOUND)

@dataclass(frozen=True)
class OnNoLocationWithCapacityExceptionEventArgs(EventArgsBase):
    storage_state: Any
    content: Content
    loc_uom_space_avail: Dict[Location, float]
    loc_states: List[LocInvState]
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_NO_LOCATION_WITH_CAPACITY_FOUND)

@dataclass(frozen=True)
class OnUoMDoesntMatchLocationActiveDesignationExceptionEventArgs(EventArgsBase):
    loc_inv: LocInvState
    uom: UnitOfMeasure
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_CONTENT_DOESNT_MATCH_LOCATION_ACTIVE_DESIGNATION)

@dataclass(frozen=True)
class OnNoLocationToRemoveContentExceptionEventArgs(EventArgsBase):
    storage_state: Any
    content: Content
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_NO_LOCATION_TO_REMOVE_CONTENT)

    def __str__(self):
        return f"{type(self).__name__} content: {self.content}"

@dataclass(frozen=True)
class OnLocationDoesNotSupportAddingContentExceptionEventArgs(EventArgsBase):
    location: Location
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_LOCATION_DOES_NOT_SUPPORT_ADDING_CONTENT)
    def __str__(self):
        return f"{type(self).__name__} {self.location} does not support adding content"


@dataclass(frozen=True)
class OnResourceUoMNotInManifestExceptionEventArgs(EventArgsBase):
    resourceUoM: ResourceUoM
    manifest: List[ResourceUoM]

    def __str__(self):
        return f"{type(self).__name__} {self.resourceUoM} not in manifest: {self.manifest}"

@dataclass(frozen=True)
class OnContainerCannotBeRemovedFromChannelType(EventArgsBase):
    location: Location
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_CONTAINER_CANNOT_BE_REMOVED_FROM_CHANNEL_TYPE)
    def __str__(self):
        return f"{type(self).__name__} Channel {self.location.channel_type} does not support removing containers"

@dataclass(frozen=True)
class OnContentCannotBeRemovedFromChannelTypeException_EventArgs(EventArgsBase):
    location: Location
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_CONTENT_CANNOT_BE_REMOVED_FROM_CHANNEL_TYPE)
    def __str__(self):
        return f"{type(self).__name__} Channel {self.location.channel_type} does not support removing content"

@dataclass(frozen=True)
class OnContainerNotInExtractablePositionExceptionEventArgs(EventArgsBase):
    inv_state: LocInvState
    container: ContainerState
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_CONTAINER_NOT_IN_EXTRACTABLE_POSITION)

@dataclass(frozen=True)
class OnContainerNotFoundException_EventArgs(EventArgsBase):
    inv_state: LocInvState
    container: Optional[ContainerState]
    event_type: StorageEventType = field(init=False,
                                         default=StorageEventType.EXCEPTION_CONTAINER_NOT_FOUND)
#endregion

#region RaiseEvents
# def raise_event_LocationNotInStorageException(args: OnLocationNotInStorageExceptionEventArgs):
#     raise_event(StorageEventType.EXCEPTION_LOCATION_NOT_IN_STORAGE, log_lvl=logging.ERROR, args=args)
#
# def raise_event_NoLocationFoundException(args: OnNoLocationFoundExceptionEventArgs):
#     raise_event(StorageEventType.EXCEPTION_NO_LOCATION_FOUND, log_lvl=logging.ERROR, args=args)
#
# def raise_event_NoLocationWithCapacityException(args: OnNoLocationWithCapacityExceptionEventArgs):
#     raise_event(StorageEventType.EXCEPTION_NO_LOCATION_WITH_CAPACITY_FOUND, log_lvl=logging.ERROR, args=args)
#
# def raise_event_ContentDoesntMatchLocationException(args: OnUoMsDontMatchUoMCapacityDefinitionExceptionEventArgs):
#     raise_event(StorageEventType.EXCEPTION_UOMS_DONT_MATCH_UOM_CAPACITY_DEFINITION, log_lvl=logging.ERROR, args=args)
#
# def raise_event_UoMDoesntMatchLocationDesignationException(args: OnUoMDoesntMatchLocationActiveDesignationExceptionEventArgs):
#     raise_event(StorageEventType.EXCEPTION_CONTENT_DOESNT_MATCH_LOCATION_ACTIVE_DESIGNATION, log_lvl=logging.ERROR, args=args)
#
# def raise_event_QtyUoMDoesntFitAtDestinationException(args: OnQtyUoMDoesntFitAtDestinationExceptionEventArgs):
#     raise_event(StorageEventType.EXCEPTION_QTY_OF_UOM_DOESNT_FIT_AT_DESTINATION, log_lvl=logging.ERROR, args=args)
#
# def raise_event_MissingContentException(args: OnMissingContentExceptionEventArgs):
#     raise_event(StorageEventType.EXCEPTION_MISSING_CONTENT, log_lvl=logging.ERROR, args=args)
#
# def raise_event_ContentNotInExtractablePositionException(args: OnMissingContentExceptionEventArgs):
#     raise_event(StorageEventType.EXCEPTION_CONTENT_NOT_IN_EXTRACTABLE_POSITION, log_lvl=logging.ERROR, args=args)
#
# def raise_event_NoLocationToRemoveContentException(args: OnNoLocationToRemoveContentExceptionEventArgs):
#     raise_event(StorageEventType.EXCEPTION_NO_LOCATION_TO_REMOVE_CONTENT, log_lvl=logging.ERROR, args=args)
#
# def raise_event_LocationDoesNotSupportAddingContentException(args: OnLocationDoesNotSupportAddingContentExceptionEventArgs):
#     raise_event(StorageEventType.EXCEPTION_LOCATION_DOES_NOT_SUPPORT_ADDING_CONTENT, log_lvl=logging.ERROR, args=args)

#endregion

class StorageException(Exception):
    def __init__(self, args: EventArgsBase):
        raise_event(args.event_type, log_lvl=logging.ERROR, args=args)
        self.user_args = args
        super().__init__(str(self.user_args))

if __name__ == "__main__":
    pass
