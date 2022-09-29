from cooptools.coopEnum import CoopEnum, auto

class ChannelType(CoopEnum):
    CONTAINER_ALL_ACCESSIBLE = auto()
    CONTAINER_FIFO_QUEUE = auto()
    CONTAINER_LIFO_QUEUE = auto()
    CONTAINER_MERGED = auto()
