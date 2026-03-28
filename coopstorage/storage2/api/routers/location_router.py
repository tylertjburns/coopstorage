from api.dataSchemas.locations_ds import LocationsSchema
import logging
from coopstorage.storage import Storage
from fastapi import APIRouter

logger = logging.getLogger(__name__)

location_router = APIRouter()

