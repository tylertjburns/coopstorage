from coopstorage.my_dataclasses import Location, location_factory, UoMCapacity, Resource
from typing import List
from coopstorage.logger import logger


def adjust_location(location: Location,
                    new_resource_limitations: List[Resource] = None,
                    removed_resource_limitations: List[Resource] = None,
                    added_uom_capacities: List[UoMCapacity] = None,
                    removed_uom_capacities: List[UoMCapacity] = None
                    ) -> Location:
    new_loc = location_factory(
        location=location,
        new_resource_limitations=new_resource_limitations,
        removed_resource_limitations=removed_resource_limitations,
        new_uom_capacities=added_uom_capacities,
        removed_uom_capacities=removed_uom_capacities
    )

    log_txt = f"{location} updated with"
    if new_resource_limitations: log_txt += f"\n\tadded resource limitations: {new_resource_limitations}"
    if removed_resource_limitations: log_txt += f"\n\tremoved resource limitations: {removed_resource_limitations}"
    if added_uom_capacities: log_txt += f"\n\tadded uom capacities: {added_uom_capacities}"
    if removed_uom_capacities: log_txt += f"\n\tremoved uom capacities: {removed_uom_capacities}"
    log_txt += f"\n\tyielding {new_loc}"

    logger.info(log_txt)

    return new_loc