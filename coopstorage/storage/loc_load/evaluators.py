"""
Standard location evaluators for use with TransferRequestCriteria.dest_loc_evaluator
and Storage.select_location().

An evaluator is a callable ``(Location) -> float`` where higher scores are preferred.
"""
import random as rnd
from coopstorage.storage.loc_load.location import Location
from cooptools.geometry_utils import vector_utils as vec


def fewest_containers(loc: Location) -> float:
    """Prefer locations with fewer containers, promoting an even spread across all locations."""
    return -len(loc.ContainerIds)

def max_available_capacity_percentage(loc: Location) -> float:
    """Prefer locations with more available capacity."""
    return loc.AvailableCapacity / loc.Capacity if loc.Capacity > 0 else 0

def least_available_capacity_percentage(loc: Location) -> float:
    """Prefer locations with more available capacity."""
    return -max_available_capacity_percentage(loc)

def random_score(loc: Location) -> float:
    """Assign a random score to each location, for random selection."""
    return rnd.random()

def distance_from(loc: Location, point: tuple[float, float, float]) -> float:
    """Calculate the Euclidean distance from the location to a given point."""
    return vec.distance_between(loc.Coords, point)