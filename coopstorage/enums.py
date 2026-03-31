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
