from coopstorage.storage2.loc_load.location import Location
import coopstorage.storage2.loc_load.dcs as dcs
from typing import Callable, Dict, Iterable, Optional
from dataclasses import dataclass
import cooptools.geometry_utils.vector_utils as vec
from cooptools.qualifiers import PatternMatchQualifier
from cooptools.protocols import UniqueIdentifier

# Callable that retrieves Load objects for a given set of IDs.
# Signature: (ids: Iterable[UniqueIdentifier]) -> Dict[UniqueIdentifier, dcs.Load]
LoadByIdProvider = Callable[[Iterable[UniqueIdentifier]], Dict[UniqueIdentifier, dcs.Load]]


def _pattern_qualifies(pattern: PatternMatchQualifier, value: str) -> bool:
    """PatternMatchQualifier.qualify() takes a list and returns a dict of results."""
    return pattern.qualify([value])[value].result


def _dims_within_max(dims, max_dims) -> bool:
    if len(dims) != len(max_dims):
        return True  # can't compare — don't disqualify
    return all(dims[ii] <= max_dims[ii] for ii in range(len(max_dims)))


def _dims_within_min(dims, min_dims) -> bool:
    if len(dims) != len(min_dims):
        return True  # can't compare — don't disqualify
    return all(dims[ii] >= min_dims[ii] for ii in range(len(min_dims)))


@dataclass(frozen=True, slots=True)
class LoadQualifier:
    pattern: Optional[PatternMatchQualifier] = None
    max_dims: Optional[vec.FloatVec] = None
    min_dims: Optional[vec.FloatVec] = None

    def check_if_qualifies(self, load: dcs.Load) -> bool:
        # Disqualify on Pattern
        if self.pattern is not None and not _pattern_qualifies(self.pattern, str(load.id)):
            return False

        # Disqualify on Max Dims
        if self.max_dims is not None and not _dims_within_max(load.uom.dimensions, self.max_dims):
            return False

        # Disqualify on Min Dims
        if self.min_dims is not None and not _dims_within_min(load.uom.dimensions, self.min_dims):
            return False

        return True


@dataclass(frozen=True, slots=True)
class LocationQualifier:
    id_pattern:  Optional[PatternMatchQualifier] = None
    max_dims:  Optional[vec.FloatVec] = None
    min_dims:  Optional[vec.FloatVec] = None
    any_loads:  Optional[Iterable[LoadQualifier]] = None
    all_loads:  Optional[Iterable[LoadQualifier]] = None
    reserved:  Optional[bool] = None
    at_least_capacity:  Optional[int] = None

    def check_if_qualifies(self,
                           loc: Location,
                           load_provider: LoadByIdProvider = None) -> bool:
        # Disqualify on Pattern
        if self.id_pattern is not None and not _pattern_qualifies(self.id_pattern, str(loc.Id)):
            return False

        # Disqualify on Max Dims
        if self.max_dims is not None and not _dims_within_max(loc.Meta.dims, self.max_dims):
            return False

        # Disqualify on Min Dims
        if self.min_dims is not None and not _dims_within_min(loc.Meta.dims, self.min_dims):
            return False

        # Disqualify if doesn't have any of any_loads
        if self.any_loads is not None:
            if load_provider is None:
                raise ValueError("load_provider is required when using any_loads qualifier")
            loc_loads = load_provider(loc.LoadIds).values()
            if not any(q.check_if_qualifies(load) for load in loc_loads for q in self.any_loads):
                return False

        # Disqualify if doesn't have all of all_loads
        if self.all_loads is not None:
            if load_provider is None:
                raise ValueError("load_provider is required when using all_loads qualifier")
            loc_loads = load_provider(loc.LoadIds).values()
            if not all(q.check_if_qualifies(load) for load in loc_loads for q in self.all_loads):
                return False

        # Disqualify on capacity
        if self.at_least_capacity is not None and loc.AvailableCapacity < self.at_least_capacity:
            return False

        # Disqualify on reserved
        if self.reserved is not None and loc.Reserved != self.reserved:
            return False

        return True
