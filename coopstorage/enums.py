from cooptools.coopEnum import CoopEnum, auto

class ChannelType(CoopEnum):
    ALL_ACCESSIBLE = auto()
    FIFO_QUEUE = auto()
    LIFO_QUEUE = auto()
    MERGED_CONTENT = auto()
