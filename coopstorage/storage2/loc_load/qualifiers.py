from coopstorage.storage2.loc_load.location import Location
import coopstorage.storage2.loc_load.dcs as dcs
from typing import Callable, Dict, Iterable, Optional
from dataclasses import dataclass
import cooptools.geometry_utils.vector_utils as vec
from cooptools.qualifiers import PatternMatchQualifier
from cooptools.protocols import UniqueIdentifier

# Callable that retrieves Container objects for a given set of IDs.
# Signature: (ids: Iterable[UniqueIdentifier]) -> Dict[UniqueIdentifier, dcs.Container]
ContainerByIdProvider = Callable[[Iterable[UniqueIdentifier]], Dict[UniqueIdentifier, dcs.Container]]


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
class ContainerQualifier:
    pattern: Optional[PatternMatchQualifier] = None
    max_dims: Optional[vec.FloatVec] = None
    min_dims: Optional[vec.FloatVec] = None

    def check_if_qualifies(self, container: dcs.Container) -> bool:
        # Disqualify on Pattern
        if self.pattern is not None and not _pattern_qualifies(self.pattern, str(container.id)):
            return False

        # Disqualify on Max Dims
        if self.max_dims is not None and not _dims_within_max(container.uom.dimensions, self.max_dims):
            return False

        # Disqualify on Min Dims
        if self.min_dims is not None and not _dims_within_min(container.uom.dimensions, self.min_dims):
            return False

        return True


@dataclass(frozen=True, slots=True)
class LocationQualifier:
    id_pattern:  Optional[PatternMatchQualifier] = None
    max_dims:  Optional[vec.FloatVec] = None
    min_dims:  Optional[vec.FloatVec] = None
    any_containers:  Optional[Iterable[ContainerQualifier]] = None
    all_containers:  Optional[Iterable[ContainerQualifier]] = None
    reserved:  Optional[bool] = None
    at_least_capacity:  Optional[int] = None
    is_occupied:  Optional[bool] = None
    has_content:  Optional[dcs.ContainerContent] = None

    def check_if_qualifies(self,
                           loc: Location,
                           container_provider: ContainerByIdProvider = None) -> bool:
        # Disqualify on Pattern
        if self.id_pattern is not None and not _pattern_qualifies(self.id_pattern, str(loc.Id)):
            return False

        # Disqualify on Max Dims
        if self.max_dims is not None and not _dims_within_max(loc.Meta.dims, self.max_dims):
            return False

        # Disqualify on Min Dims
        if self.min_dims is not None and not _dims_within_min(loc.Meta.dims, self.min_dims):
            return False

        # Disqualify if doesn't have any of any_containers
        if self.any_containers is not None:
            if container_provider is None:
                raise ValueError("container_provider is required when using any_containers qualifier")
            loc_containers = container_provider(loc.ContainerIds).values()
            if not any(q.check_if_qualifies(container) for container in loc_containers for q in self.any_containers):
                return False

        # Disqualify if doesn't have all of all_containers
        if self.all_containers is not None:
            if container_provider is None:
                raise ValueError("container_provider is required when using all_containers qualifier")
            loc_containers = container_provider(loc.ContainerIds).values()
            if not all(q.check_if_qualifies(container) for container in loc_containers for q in self.all_containers):
                return False

        # Disqualify on capacity
        if self.at_least_capacity is not None and loc.AvailableCapacity < self.at_least_capacity:
            return False

        # Disqualify on reserved
        if self.reserved is not None and loc.Reserved != self.reserved:
            return False

        # Disqualify on occupied state: True requires at least one container, False requires none
        if self.is_occupied is not None:
            occupied = len(loc.ContainerIds) > 0
            if occupied != self.is_occupied:
                return False

        # Disqualify if total qty of (resource, uom) across all containers is less than required
        if self.has_content is not None:
            if container_provider is None:
                raise ValueError("container_provider is required when using has_content qualifier")
            loc_containers = container_provider(loc.ContainerIds).values()
            total = sum(
                c.qty
                for container in loc_containers
                for c in container.contents
                if c.resource == self.has_content.resource and c.uom == self.has_content.uom
            )
            if total < self.has_content.qty:
                return False

        return True
