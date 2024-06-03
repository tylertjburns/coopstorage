import logging
from coopapi import http_request_handlers as hrh
from coopapi.apiShell import ApiShell, RequestCallbackPackage
from dataclasses import dataclass
from coopstorage.my_dataclasses.channel import ChannelProcessor, ChannelMeta, ChannelState
from typing import List, Dict
import uuid
import re
from api.routers.router_factory import RequestCallbackPackage, CrUDOperations, router_factory
from fastapi import APIRouter
from coopapi.enums import RequestType

logger = logging.getLogger('locations_router')

@dataclass
class ChannelsMetaSchema:
    channels: List[ChannelMeta]

@dataclass
class ChannelsStateSchema:
    channels: Dict[str|uuid.UUID, ChannelState]

class Channels:
    def __init__(self):
        self.channels: Dict[str|uuid.UUID, ChannelProcessor] = {}

    def add(self, cp: ChannelsMetaSchema):
        for x in cp.channels:
            hrh.http_verify_not_duplicate(lambda: x.id not in self.channels.keys(), x.id)

        cp.channels = list(set(cp.channels))

        for x in cp.channels:
            self.channels[x.id] = ChannelProcessor(x)

        return ChannelsStateSchema(
            channels={k: v.State for k, v in self.channels.items() if k in [x.id for x in cp.channels]}
        )

    def delete(self, id: str|uuid.UUID):
        if id in self.channels.keys():
            del self.channels[id]
            return True
        return False

    def find(self, id: str|uuid.UUID):
        hrh.http_verify_entity_exists(lambda : self.channels.get(id, None) is not None, id)
        return ChannelsStateSchema(channels={id: self.channels.get(id, None).State})

    def query(self,
              id_regex: str = None):
        matches = [x for x in self.channels.keys() if re.search(id_regex, x) is not None]
        return ChannelsStateSchema(channels={k: v.State for k, v in self.channels.items() if k in matches})


    def get(self):
        return ChannelsStateSchema(channels={k: v.State for k, v in self.channels.items()})

def channel_router_factory(channels: Channels):
    base_route = '/channels/api/'

    channel_router = APIRouter()

    channel_router.add_api_route(path=base_route,
                                 endpoint=channels.add,
                                 methods=[RequestType.POST.value],
                                 response_description=f"{RequestType.POST.value} a new {self.response_schema.__name__}",
                                 response_model=self.response_schema,
                                 status_code=_success_status_code.get(request_type_map.get(self.operation))
                         )








    request_callbacks = [
        RequestCallbackPackage(
            operation=CrUDOperations.ADD,
            callback=channels.add,
            input_body_schema=ChannelsMetaSchema,
            response_schema=ChannelsStateSchema,
        ),
        RequestCallbackPackage(
            operation=CrUDOperations.GETALL,
            callback=channels.get,
            response_schema=ChannelsStateSchema,
        ),
        RequestCallbackPackage(
            operation=CrUDOperations.GETONE,
            callback=channels.find,
            response_schema=ChannelsStateSchema,
            path_paramaters=['id']
        ),
        RequestCallbackPackage(
            operation=CrUDOperations.DELETE,
            callback=channels.delete,
            response_schema=ChannelsStateSchema,
            path_paramaters=['id']
        ),
        RequestCallbackPackage(
            operation=CrUDOperations.QUERY,
            callback=channels.query,
            response_schema=ChannelsStateSchema
        )
    ]
    # create_cb_pac = RequestCallbackPackage(
    #     method=RequestType.POST,
    #     callback=lambda req, T: channels.add(T),
    #     input_body_schema=ChannelsMetaSchema,
    #     response_schema=ChannelsStateSchema,
    # )
    #
    # list_cb_pac = RequestCallbackPackage(
    #     method=RequestType.GET,
    #     callback=lambda req, T: channels.get(),
    #     input_body_schema=None,
    #     response_schema=ChannelsStateSchema,
    # )

    channel_router = router_factory(base_route, request_callbacks)

    return channel_router