from coopstorage.my_dataclasses import Location, location_factory, UoMCapacity, Resource
from typing import List
from coopstorage.logger import logger

def add_uom_capacities(location: Location, new_uom_capacities: List[UoMCapacity]) -> Location:
    return location_factory(
        location=location,
        new_uom_capacities=new_uom_capacities
    )

def remove_uom_capacities(location: Location, removed_uom_capacities: List[UoMCapacity]) -> Location:
    return location_factory(
        location=location,
        removed_uom_capacities=removed_uom_capacities
    )

def add_resource_limitations(location: Location, new_resource_limitations: List[Resource]) -> Location:
    new_loc = location_factory(
        location=location,
        new_resource_limitations=new_resource_limitations
    )

    logger.info(f"{location} updated with new resource constraints {new_resource_limitations} from {location} yielding {new_loc}")

    return new_loc

def remove_resource_limitations(location: Location, removed_resource_limitations: List[Resource]) -> Location:
    return location_factory(
        location=location,
        removed_resource_limitations=removed_resource_limitations
    )