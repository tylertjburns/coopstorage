"""
Standard location evaluators for use with TransferRequestCriteria.dest_loc_evaluator
and Storage.select_location().

An evaluator is a callable ``(Location) -> float`` where higher scores are preferred.
"""

from coopstorage.storage.loc_load.location import Location


def fewest_containers(loc: Location) -> float:
    """Prefer locations with fewer containers, promoting an even spread across all locations."""
    return -len(loc.ContainerIds)
