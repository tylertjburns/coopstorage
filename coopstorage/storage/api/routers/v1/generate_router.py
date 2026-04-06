import logging
from dataclasses import replace
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from coopstorage.storage.loc_load.storage import Storage
import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.channel_processors as cps
from coopstorage.storage_generators import (
    BayConfig, AisleConfig, ZoneConfig, StorageConfig,
)

logger = logging.getLogger(__name__)


class BayConfigAPI(BaseModel):
    loc_dims: List[float] = [10.0, 10.0, 5.0]
    channel_processor_type: str = "AllAvailable"
    capacity: int = 1
    locations_per_bay: int = 2
    inter_bay_spacing: float = 2.0
    bay_height: float = 6.0
    shelves: int = 5
    side_designator: str = "L"

    def as_bay_config(self) -> BayConfig:
        return BayConfig(
            loc_config=dcs.LocationMeta(
                dims=tuple(self.loc_dims),
                channel_processor=cps.ChannelProcessorType.by_str(self.channel_processor_type).value,
                capacity=self.capacity,
            ),
            locations_per_bay=self.locations_per_bay,
            inter_bay_spacing=self.inter_bay_spacing,
            bay_height=self.bay_height,
            shelves=self.shelves,
            side_designator=self.side_designator,
        )


class AisleConfigAPI(BaseModel):
    bays: int = 10
    aisle_width: float = 20.0
    left_bay: Optional[BayConfigAPI] = None
    right_bay: Optional[BayConfigAPI] = None

    def as_aisle_config(self) -> AisleConfig:
        left = replace(self.left_bay.as_bay_config(), side_designator="L") if self.left_bay else None
        right = replace(self.right_bay.as_bay_config(), side_designator="R") if self.right_bay else None
        return AisleConfig(
            bays=self.bays,
            aisle_width=self.aisle_width,
            left_bay_config=left,
            right_bay_config=right,
        )


class ZoneConfigAPI(BaseModel):
    aisles: int = 5
    inter_aisle_spacing: float = 20.0
    origin: List[float] = [0.0, 0.0, 0.0]
    aisle_config: AisleConfigAPI = None

    def as_zone_config(self) -> ZoneConfig:
        aisle_cfg = self.aisle_config.as_aisle_config() if self.aisle_config else AisleConfig()
        return ZoneConfig(
            aisles=self.aisles,
            inter_aisle_spacing=self.inter_aisle_spacing,
            origin=tuple(self.origin),
            aisle_config=aisle_cfg,
        )


class GenerateStorageAPI(BaseModel):
    zones: List[ZoneConfigAPI]


def generate_router_factory(storage: Storage) -> APIRouter:
    router = APIRouter(prefix="/storage", tags=["generate"])

    @router.post("/generate")
    def generate_storage(body: GenerateStorageAPI):
        """Generate and register locations from a structured storage config.

        Populates the live storage (and its LocationMapTree) in-place.
        Returns a summary of what was registered.
        """
        config = StorageConfig(
            zones_config=[z.as_zone_config() for z in body.zones]
        )
        tree = storage.LocationMapTree
        locs = config.locs(tree=tree)
        storage.register_locs(locs=locs)
        logger.info(f"Generated {len(locs)} locations across {len(body.zones)} zone(s)")
        return {
            "registered": len(locs),
            "zones": len(body.zones),
        }

    return router
