from api.dataSchemas.locations_ds import LocationsSchema
import logging
from coopapi import http_request_handlers as hrh
from coopstorage.storage import Storage
from coopapi.apiShell import ApiShell

logger = logging.getLogger('locations_router')


def location_router_factory(storage: Storage):
    create_location_cb: hrh.postRequestCallback = lambda req, T: storage.add_locations(T.location_data_store)
    delete_location_cb: hrh.deleteRequestCallback = lambda req, id: storage.remove_locations(locations=[
        storage.location_by_id(id)
    ])
    find_cb: hrh.getOneRequestCallback = lambda req, id: storage.location_by_id(id)
    get_locations_cb: hrh.getManyRequestCallback = lambda req, query, count: storage.state.Locations

    location_router = ApiShell(target_schema=LocationsSchema,
                               on_post_callback=create_location_cb,
                               on_delete_callback=delete_location_cb,
                               on_getone_callback=find_cb,
                               on_getmany_callback=get_locations_cb,
                               base_route='/locations')
    return location_router