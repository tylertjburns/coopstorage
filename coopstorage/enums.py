from cooptools.coopEnum import CoopEnum, auto


class ChannelType(CoopEnum):
    ALL_ACCESSIBLE = auto()
    FIFO_QUEUE = auto()
    LIFO_QUEUE = auto()
    MERGED_CONTENT = auto()


class StorageTopic(CoopEnum):
    """pypubsub topic names for internal storage events."""
    LOCATION_REGISTERED  = 'storage.location_registered'
    CONTAINER_REGISTERED = 'storage.container_registered'
    CONTAINER_MOVED      = 'storage.container_moved'
    CONTENT_CHANGED      = 'storage.content_changed'
    CONTAINER_REMOVED    = 'storage.container_removed'
    CONTAINER_RESERVED   = 'storage.container_reserved'
    CONTAINER_UNRESERVED = 'storage.container_unreserved'
    LOCATION_RESERVED    = 'storage.location_reserved'
    LOCATION_UNRESERVED  = 'storage.location_unreserved'
    RESERVATION_FAILED         = 'storage.reservation_failed'
    TRANSFER_REQUEST_ADDED     = 'storage.transfer_request_added'
    TRANSFER_REQUEST_COMPLETED = 'storage.transfer_request_completed'
