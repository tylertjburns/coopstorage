import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataclasses import dataclass, field
from typing import Iterable, Dict
import logging
from coopstorage.storage.loc_load.location import Location
from cooptools.geometry_utils import vector_utils as vec
import coopstorage.storage.loc_load.dcs as dcs
from coopstorage.storage.loc_load.storage import Storage
import coopstorage.storage.loc_load.channel_processors as cps

@dataclass(frozen=True, slots=True)
class ShelfConfig:
    loc_config: dcs.LocationMeta

@dataclass(frozen=True, slots=True)
class BayConfig:
    locations_per_bay: int = 2
    inter_bay_spacing: float = 10.0
    bay_height: float = 5.0
    shelves: int = 5
    shelf_config: ShelfConfig = field(default_factory=ShelfConfig)

@dataclass(frozen=True, slots=True)
class AisleConfig:
    bays: int = 100
    bay_config: BayConfig = field(default_factory=BayConfig)

@dataclass(frozen=True, slots=True)
class ZoneConfig:
    aisles: int = 10
    aisle_config: AisleConfig = field(default_factory=AisleConfig)
    inter_aisle_spacing: float = 20.0
    zone_origin: vec.FloatVec = (0.0, 0.0, 0.0)

@dataclass(frozen=True, slots=True)
class StorageConfig:
    zones: int = 1
    zone_config: ZoneConfig = field(default_factory=ZoneConfig)


# def build_aisle() -> Iterable[Location]:
#     locations = [
#         Location(
#             id=f"{cp.__name__}_{i:04d}",
#             location_meta=dcs.LocationMeta(
#                 dims=(10, 10, 5),
#                 channel_processor=cp(),
#                 capacity=cfg.location_capacity,
#             ),
#             coords=(type_idx * _LOC_SPACING, i * _LOC_SPACING, 0),
#         )
#         for type_idx, cp in enumerate(CHANNEL_PROCESSOR_TYPES)
#         for i in range(cfg.locs_per_type)
#     ]
#     return Storage(locs=locations)

def build_storage(config: StorageConfig) -> Storage:
    locations = []
    for zone_idx in range(config.zones):
        zone_origin = vec.add_vectors([config.zone_config.zone_origin, (0, zone_idx * config.zone_config.inter_aisle_spacing, 0)])
        for aisle_idx in range(config.zone_config.aisles):
            aisle_origin = vec.add_vectors([zone_origin, (0, aisle_idx * config.zone_config.inter_aisle_spacing, 0)])
            for bay_idx in range(config.zone_config.aisle_config.bays):
                bay_origin = vec.add_vectors([aisle_origin, (bay_idx * (config.zone_config.aisle_config.bay_config.shelf_config.loc_config.dims[0] * config.zone_config.aisle_config.bay_config.locations_per_bay + config.zone_config.aisle_config.bay_config.inter_bay_spacing), 0, 0)])
                for shelf_idx in range(config.zone_config.aisle_config.bay_config.shelves):
                    shelf_origin = vec.add_vectors([bay_origin, (0, 0, shelf_idx * config.zone_config.aisle_config.bay_config.bay_height)])
                    for loc_idx in range(config.zone_config.aisle_config.bay_config.locations_per_bay):
                        loc_coords = vec.add_vectors([shelf_origin, (loc_idx * config.zone_config.aisle_config.bay_config.shelf_config.loc_config.dims[0], 0, 0)])
                        locations.append(Location(
                            id=f"Zone{zone_idx}_Aisle{aisle_idx}_Bay{bay_idx}_Shelf{shelf_idx}_Loc{loc_idx}",
                            location_meta=config.zone_config.aisle_config.bay_config.shelf_config.loc_config,
                            coords=loc_coords,
                        ))
    return Storage(locs=locations)

if __name__ == "__main__":
    from pprint import pprint
    from coopstorage.viz_helper import start_visualizer
    
    def test_build_storage_001():
        storage = build_storage(
            config=StorageConfig(
                zones=1,
                zone_config=ZoneConfig(
                    aisles=5,
                    aisle_config=AisleConfig(
                        bays=10,
                        bay_config=BayConfig(
                            locations_per_bay=2,
                            inter_bay_spacing=5.0,
                            bay_height=6.0,
                            shelves=7,
                            shelf_config=ShelfConfig(
                                loc_config=dcs.LocationMeta(
                                    dims=(10, 10, 5),
                                    channel_processor=cps.AllAvailableChannelProcessor(),
                                    capacity=1,
                                )
                            )
                        ),
                    ),
                    inter_aisle_spacing=25.0,
                    zone_origin=(0.0, 0.0, 0.0),
                )
            )
        )
        print(f"Built storage with {len(storage.Locations)} locations")
        start_visualizer(storage, block=True)
        
    test_build_storage_001()
