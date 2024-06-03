from dataclasses import dataclass
from coopstorage.my_dataclasses.channel import ChannelProcessor, ChannelMeta, ChannelState
from typing import List

@dataclass
class AddChannelsSchema:
    channels: List[ChannelMeta]




