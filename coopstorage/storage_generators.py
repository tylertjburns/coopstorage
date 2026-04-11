import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataclasses import dataclass, field, replace
from typing import Iterable, Dict, List
import logging
from coopstorage.storage.loc_load.location import Location
from cooptools.geometry_utils import vector_utils as vec
import coopstorage.storage.loc_load.dcs as dcs
from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.reservation_provider import ReservationProvider
import coopstorage.storage.loc_load.channel_processors as cps
from coopstorage.location_map_tree import LocationMapTree
import math

@dataclass(frozen=True, slots=True)
class BayConfig:
    loc_config: dcs.LocationMeta
    locations_per_bay: int = 2
    inter_bay_spacing: float = 3.0
    bay_height: float = 5.0
    shelves: int = 5
    side_designator: str = "L"  # for visualizer only; can be "L" or "R"
    
    def locs(self,
            zone_idx: int,
            aisle_idx: int,
            bay_idx: int,
            bay_origin: vec.FloatVec,
            tree: LocationMapTree = None,
    ) -> List[Location]:
        locations = []

        for shelf_idx in range(self.shelves):
            shelf_origin = vec.add_vectors([bay_origin, (0, 0, shelf_idx * self.bay_height)])
            for loc_idx in range(self.locations_per_bay):
                loc_coords = vec.add_vectors([shelf_origin, (loc_idx * self.loc_config.dims[0], 0, 0)])
                loc_id = f"Zone{zone_idx}_Aisle{aisle_idx}_Bay{bay_idx}{self.side_designator}_Shelf{shelf_idx}_Loc{loc_idx}"
                locations.append(Location(
                    id=loc_id,
                    location_meta=self.loc_config,
                    coords=loc_coords,
                ))
                if tree is not None:
                    tree.register(
                        loc_id,
                        zone=zone_idx,
                        aisle=aisle_idx,
                        row=f"{aisle_idx}{self.side_designator}",
                        bay=f"{bay_idx}{self.side_designator}",
                        shelf=shelf_idx,
                        loc=loc_idx,
                    )

        return locations

@dataclass(frozen=True, slots=True)
class AisleConfig:
    bays: int = 20
    left_bay_config: BayConfig = None
    right_bay_config: BayConfig = None
    aisle_width: float = 20.0

    def net_aisle_width(self) -> float:
        width = self.aisle_width
        if self.left_bay_config is not None:
            width += self.left_bay_config.loc_config.dims[1]
        if self.right_bay_config is not None:
            width += self.right_bay_config.loc_config.dims[1]
        return width

    def locs(self, zone_idx: int, aisle_idx: int, aisle_origin: vec.FloatVec, tree: LocationMapTree = None) -> List[Location]:
        locations = []
        for bay_idx in range(self.bays):
            if self.left_bay_config is not None:
                bay_origin = vec.add_vectors([aisle_origin, (bay_idx * (self.left_bay_config.loc_config.dims[0] * self.left_bay_config.locations_per_bay + self.left_bay_config.inter_bay_spacing), self.aisle_width + self.left_bay_config.loc_config.dims[1], 0)])
                locations.extend(self.left_bay_config.locs(zone_idx, aisle_idx, bay_idx, bay_origin, tree=tree))

            if self.right_bay_config is not None:
                bay_origin = vec.add_vectors([aisle_origin, (bay_idx * (self.right_bay_config.loc_config.dims[0] * self.right_bay_config.locations_per_bay + self.right_bay_config.inter_bay_spacing), 0, 0)])
                locations.extend(self.right_bay_config.locs(zone_idx, aisle_idx, bay_idx, bay_origin, tree=tree))

        return locations
    
@dataclass(frozen=True, slots=True)
class ZoneConfig:
    aisles: int = 10
    aisle_config: AisleConfig = field(default_factory=AisleConfig)
    inter_aisle_spacing: float = 2.0
    origin: vec.FloatVec = (0.0, 0.0, 0.0)

    def locs(self, zone_idx: int = 0, tree: LocationMapTree = None) -> List[Location]:
        locations = []
        for aisle_idx in range(self.aisles):
            aisle_origin = vec.add_vectors([self.origin, (0, aisle_idx * (self.inter_aisle_spacing + self.aisle_config.net_aisle_width()), 0)])
            locations.extend(self.aisle_config.locs(zone_idx, aisle_idx, aisle_origin, tree=tree))
        return locations

@dataclass(frozen=True, slots=True)
class StorageConfig:
    zones_config: Iterable[ZoneConfig] = field(default_factory=list)

    def locs(self, tree: LocationMapTree = None) -> List[Location]:
        locations = []
        for zone_idx, zone_config in enumerate(self.zones_config):
            locations.extend(zone_config.locs(zone_idx=zone_idx, tree=tree))
        return locations

    def storage(self, reservation_provider: ReservationProvider = None) -> Storage:
        tree = LocationMapTree()
        return Storage(locs=self.locs(tree=tree), location_map_tree=tree, reservation_provider=reservation_provider)

def build_all_processor_storage(
    locs_per_type: int = 3,
    location_capacity: int = 5,
    loc_spacing: float = 15.0,
    reservation_provider: ReservationProvider = None,
) -> Storage:
    """Build a Storage with N locations per channel processor type, arranged in
    parallel rows — one row per processor type."""
    from coopstorage.storage.loc_load.location import Location
    locations = [
        Location(
            id=f"{cp.name}_{i:04d}",
            location_meta=dcs.LocationMeta(
                dims=(10, 10, 5),
                channel_processor=cp.value,
                capacity=location_capacity,
            ),
            coords=(type_idx * loc_spacing, i * loc_spacing, 0),
        )
        for type_idx, cp in enumerate(cps.ChannelProcessorType)
        for i in range(locs_per_type)
    ]
    return Storage(locs=locations, reservation_provider=reservation_provider)


def build_showcase_storage(
    location_capacity: int = 5,
    loc_spacing: float = 15.0,
    reservation_provider: ReservationProvider = None,
) -> Storage:
    """Build a Storage with exactly one location per channel processor type,
    arranged in the smallest square grid that fits all types."""
    n    = len(cps.ChannelProcessorType)
    cols = math.ceil(math.sqrt(n))
    locations = [
        Location(
            id=cp_type.name,
            location_meta=dcs.LocationMeta(
                dims=(10, 10, 5),
                channel_processor=cp_type.value,
                capacity=location_capacity,
            ),
            coords=((idx % cols) * loc_spacing, (idx // cols) * loc_spacing, 0),
        )
        for idx, cp_type in enumerate(cps.ChannelProcessorType)
    ]
    return Storage(locs=locations, reservation_provider=reservation_provider)


if __name__ == "__main__":
    from pprint import pprint
    from coopstorage.viz_helper import start_visualizer
    
    def test_build_storage_001():
        bay = BayConfig(
            locations_per_bay=2,
            inter_bay_spacing=2.0,
            bay_height=6.0,
            shelves=10,
            loc_config=dcs.LocationMeta(
                dims=(10, 10, 5),
                channel_processor=cps.AllAvailableChannelProcessor(),
                capacity=1
            )
        )


        storage = StorageConfig(
                zones_config=[ZoneConfig(
                    aisles=20,
                    aisle_config=AisleConfig(
                        bays=20,
                        left_bay_config=replace(bay, side_designator="L"),
                        right_bay_config=replace(bay, side_designator="R"),
                        aisle_width=20.0
                    ),
                    inter_aisle_spacing=2.0,
                    origin=(0.0, 0.0, 0.0),
                )]
            ).storage()
        
        print(f"Built storage with {len(storage.Locations)} locations")
        start_visualizer(storage, block=True)
        
    test_build_storage_001()
