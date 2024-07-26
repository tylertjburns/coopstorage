from coopstorage.storage2.loc_load.location import Location
import coopstorage.storage2.loc_load.dcs as dcs
from typing import Iterable, List
import re
from dataclasses import dataclass
import cooptools.geometry_utils.vector_utils as vec
import coopstorage.storage2.loc_load.dcs as dcs


@dataclass(frozen=True, slots=True)
class LoadQualifier:
    pattern: dcs.PatternMatchQuery = None
    max_dims: vec.FloatVec = None
    min_dims: vec.FloatVec = None

    def check_if_qualifies(self, load: dcs.Load) -> bool:
        # Disqualify on Pattern
        if self.pattern is not None and not self.pattern.check_if_matches(str(load.id)):
            return False

        # Disqualify on Max Dims
        if self.max_dims is not None and vec.verify_len_match(self.max_dims,
                                                              load.uom.dimensions,
                                                              block=False):
            smaller = all(load.uom.dimensions[ii] <= self.max_dims[ii] for ii in len(self.max_dims))
            if not smaller:
                return False

        # Disqualify on Min Dims
        if self.min_dims is not None and vec.verify_len_match(self.min_dims,
                                                              load.uom.dimensions,
                                                              block=False):
            bigger = all(load.uom.dimensions[ii] >= self.max_dims[ii] for ii in len(self.min_dims))
            if not bigger:
                return False

        return True



@dataclass(frozen=True, slots=True)
class LocationQualifier:
    pattern: dcs.PatternMatchQuery = None
    max_dims: vec.FloatVec = None
    min_dims: vec.FloatVec = None
    any_loads: Iterable[LoadQualifier] = None
    all_loads: Iterable[LoadQualifier] = None
    reserved: bool = None
    at_least_capacity: int = None

    def check_if_qualifies(self, loc: Location) -> bool:
        # Disqualify on Pattern
        if self.pattern is not None and not self.pattern.check_if_matches(str(loc.Id)):
            return False

        #Disqualify on Max Dims
        if self.max_dims is not None and vec.verify_len_match(self.max_dims,
                                                              loc.Meta.dims,
                                                              block=False):
            smaller = all(loc.Meta.dims[ii] <= self.max_dims[ii] for ii in len(self.max_dims))
            if not smaller:
                return False

        # Disqualify on Min Dims
        if self.min_dims is not None and vec.verify_len_match(self.min_dims,
                                                              loc.Meta.dims,
                                                              block=False):
            bigger = all(loc.Meta.dims[ii] >= self.max_dims[ii] for ii in len(self.min_dims))
            if not bigger:
                return False

        # Disqualify if doesnt have any of any_loads
        if self.any_loads is not None and not any(x.check_if_qualifies(y) for y in loc.LoadIds for x in self.any_loads):
            return False

        # Disqualify if doesnt have all of all_loads
        if self.any_loads is not None and not all(x.check_if_qualifies(y) for y in loc.LoadIds for x in self.all_loads):
            return False

        # Disqualify on capacity
        if self.at_least_capacity is not None and loc.AvailableCapacity < self.at_least_capacity:
            return False

        # Disqualify on reserved
        if self.reserved is not None and loc.Reserved != self.reserved:
            return False

        return True

