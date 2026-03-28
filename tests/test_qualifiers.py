"""
Tests for qualifiers.py

Covers:
- LoadQualifier: pattern, max_dims, min_dims
- LocationQualifier: id_pattern, max_dims, min_dims, any_loads, all_loads,
                     at_least_capacity, reserved
"""
import unittest
import uuid

import coopstorage.storage2.loc_load.dcs as dcs
import coopstorage.storage2.loc_load.channel_processors as cps
from coopstorage.storage2.loc_load.location import Location
from coopstorage.storage2.loc_load.qualifiers import LoadQualifier, LocationQualifier
from cooptools.qualifiers import PatternMatchQualifier

# ── fixtures ──────────────────────────────────────────────────────────────────

EA = dcs.UnitOfMeasure(name='EA', dimensions=(1.0, 1.0, 1.0))
BIG = dcs.UnitOfMeasure(name='BIG', dimensions=(5.0, 5.0, 5.0))

def _load(id='L1', uom=EA):
    return dcs.Load(id=id, uom=uom)

def _loc(id='A', capacity=3, dims=(10.0, 10.0, 10.0)):
    return Location(
        id=id,
        location_meta=dcs.LocationMeta(
            dims=dims,
            channel_processor=cps.AllAvailableChannelProcessor(),
            capacity=capacity,
        ),
        coords=(0, 0, 0),
    )


# ── LoadQualifier ─────────────────────────────────────────────────────────────

class TestLoadQualifier(unittest.TestCase):

    def test_no_criteria_always_qualifies(self):
        q = LoadQualifier()
        self.assertTrue(q.check_if_qualifies(_load()))

    def test_pattern_match_pass(self):
        q = LoadQualifier(pattern=PatternMatchQualifier(regex='^L'))
        self.assertTrue(q.check_if_qualifies(_load(id='L1')))

    def test_pattern_match_fail(self):
        q = LoadQualifier(pattern=PatternMatchQualifier(regex='^Z'))
        self.assertFalse(q.check_if_qualifies(_load(id='L1')))

    def test_max_dims_qualifies_when_smaller(self):
        q = LoadQualifier(max_dims=(2.0, 2.0, 2.0))
        self.assertTrue(q.check_if_qualifies(_load(uom=EA)))  # EA dims = (1,1,1)

    def test_max_dims_disqualifies_when_larger(self):
        q = LoadQualifier(max_dims=(0.5, 0.5, 0.5))
        self.assertFalse(q.check_if_qualifies(_load(uom=EA)))  # EA dims = (1,1,1)

    def test_min_dims_qualifies_when_larger(self):
        q = LoadQualifier(min_dims=(0.5, 0.5, 0.5))
        self.assertTrue(q.check_if_qualifies(_load(uom=EA)))  # EA dims = (1,1,1)

    def test_min_dims_disqualifies_when_smaller(self):
        q = LoadQualifier(min_dims=(2.0, 2.0, 2.0))
        self.assertFalse(q.check_if_qualifies(_load(uom=EA)))  # EA dims = (1,1,1)

    def test_combined_criteria(self):
        q = LoadQualifier(
            pattern=PatternMatchQualifier(regex='^L'),
            max_dims=(2.0, 2.0, 2.0),
            min_dims=(0.5, 0.5, 0.5),
        )
        self.assertTrue(q.check_if_qualifies(_load(id='L1', uom=EA)))

    def test_combined_criteria_fails_on_pattern(self):
        q = LoadQualifier(
            pattern=PatternMatchQualifier(regex='^Z'),
            max_dims=(2.0, 2.0, 2.0),
        )
        self.assertFalse(q.check_if_qualifies(_load(id='L1', uom=EA)))


# ── LocationQualifier ─────────────────────────────────────────────────────────

class TestLocationQualifier(unittest.TestCase):

    def test_no_criteria_always_qualifies(self):
        q = LocationQualifier()
        self.assertTrue(q.check_if_qualifies(_loc()))

    def test_id_pattern_pass(self):
        q = LocationQualifier(id_pattern=PatternMatchQualifier(regex='^A'))
        self.assertTrue(q.check_if_qualifies(_loc(id='Alpha')))

    def test_id_pattern_fail(self):
        q = LocationQualifier(id_pattern=PatternMatchQualifier(regex='^Z'))
        self.assertFalse(q.check_if_qualifies(_loc(id='Alpha')))

    def test_at_least_capacity_pass(self):
        loc = _loc(capacity=5)
        loc.store_loads(['L1'])  # 4 available
        q = LocationQualifier(at_least_capacity=4)
        self.assertTrue(q.check_if_qualifies(loc))

    def test_at_least_capacity_fail(self):
        loc = _loc(capacity=3)
        loc.store_loads(['L1', 'L2'])  # 1 available
        q = LocationQualifier(at_least_capacity=2)
        self.assertFalse(q.check_if_qualifies(loc))

    def test_reserved_filter_true(self):
        loc = _loc()
        loc.set_reservation_token(uuid.uuid4())
        q = LocationQualifier(reserved=True)
        self.assertTrue(q.check_if_qualifies(loc))

    def test_reserved_filter_false(self):
        loc = _loc()
        q = LocationQualifier(reserved=False)
        self.assertTrue(q.check_if_qualifies(loc))

    def test_reserved_filter_excludes_reserved(self):
        loc = _loc()
        loc.set_reservation_token(uuid.uuid4())
        q = LocationQualifier(reserved=False)
        self.assertFalse(q.check_if_qualifies(loc))

    def test_max_dims_qualifies(self):
        loc = _loc(dims=(5.0, 5.0, 5.0))
        q = LocationQualifier(max_dims=(10.0, 10.0, 10.0))
        self.assertTrue(q.check_if_qualifies(loc))

    def test_max_dims_disqualifies(self):
        loc = _loc(dims=(15.0, 15.0, 15.0))
        q = LocationQualifier(max_dims=(10.0, 10.0, 10.0))
        self.assertFalse(q.check_if_qualifies(loc))

    def test_min_dims_qualifies(self):
        loc = _loc(dims=(15.0, 15.0, 15.0))
        q = LocationQualifier(min_dims=(10.0, 10.0, 10.0))
        self.assertTrue(q.check_if_qualifies(loc))

    def test_min_dims_disqualifies(self):
        loc = _loc(dims=(5.0, 5.0, 5.0))
        q = LocationQualifier(min_dims=(10.0, 10.0, 10.0))
        self.assertFalse(q.check_if_qualifies(loc))

    def _make_load_provider(self, loads):
        """Build a LoadByIdProvider backed by a simple dict of Load objects."""
        load_map = {l.id: l for l in loads}
        return lambda ids: {i: load_map[i] for i in ids if i in load_map}

    def test_any_loads_qualifier_pass(self):
        """Location qualifies if at least one load matches any_loads qualifier."""
        loc = _loc(capacity=5)
        loc.store_loads(['L1'])
        provider = self._make_load_provider([dcs.Load(id='L1')])
        q = LocationQualifier(
            any_loads=[LoadQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertTrue(q.check_if_qualifies(loc, load_provider=provider))

    def test_any_loads_qualifier_fail(self):
        """Location fails if no loads match any_loads qualifier."""
        loc = _loc(capacity=5)
        loc.store_loads(['X1'])
        provider = self._make_load_provider([dcs.Load(id='X1')])
        q = LocationQualifier(
            any_loads=[LoadQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertFalse(q.check_if_qualifies(loc, load_provider=provider))

    def test_all_loads_qualifier_pass(self):
        """Location qualifies if all loads match all_loads qualifier."""
        loc = _loc(capacity=5)
        loc.store_loads(['L1', 'L2'])
        provider = self._make_load_provider([dcs.Load(id='L1'), dcs.Load(id='L2')])
        q = LocationQualifier(
            all_loads=[LoadQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertTrue(q.check_if_qualifies(loc, load_provider=provider))

    def test_all_loads_qualifier_fail(self):
        """Location fails if any load doesn't match all_loads qualifier."""
        loc = _loc(capacity=5)
        loc.store_loads(['L1', 'X1'])
        provider = self._make_load_provider([dcs.Load(id='L1'), dcs.Load(id='X1')])
        q = LocationQualifier(
            all_loads=[LoadQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertFalse(q.check_if_qualifies(loc, load_provider=provider))

    def test_any_loads_without_provider_raises(self):
        """any_loads qualifier without a load_provider should raise."""
        loc = _loc(capacity=5)
        loc.store_loads(['L1'])
        q = LocationQualifier(
            any_loads=[LoadQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        with self.assertRaises(ValueError):
            q.check_if_qualifies(loc)

    def test_combined_criteria(self):
        loc = _loc(id='A', capacity=5, dims=(10.0, 10.0, 10.0))
        loc.store_loads(['L1'])
        q = LocationQualifier(
            id_pattern=PatternMatchQualifier(regex='^A'),
            at_least_capacity=2,
            reserved=False,
        )
        self.assertTrue(q.check_if_qualifies(loc))


if __name__ == "__main__":
    unittest.main()
