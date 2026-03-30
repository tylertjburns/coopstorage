"""
Tests for qualifiers.py

Covers:
- ContainerQualifier: pattern, max_dims, min_dims
- LocationQualifier: id_pattern, max_dims, min_dims, any_loads, all_loads,
                     at_least_capacity, reserved
"""
import unittest
import uuid

import coopstorage.storage2.loc_load.dcs as dcs
import coopstorage.storage2.loc_load.channel_processors as cps
from coopstorage.storage2.loc_load.location import Location
from coopstorage.storage2.loc_load.qualifiers import ContainerQualifier, LocationQualifier
from cooptools.qualifiers import PatternMatchQualifier

# ── fixtures ──────────────────────────────────────────────────────────────────

EA = dcs.UnitOfMeasure(name='EA', dimensions=(1.0, 1.0, 1.0))
BIG = dcs.UnitOfMeasure(name='BIG', dimensions=(5.0, 5.0, 5.0))

def _load(id='L1', uom=EA):
    return dcs.Container(id=id, uom=uom)

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


# ── ContainerQualifier ────────────────────────────────────────────────────────

class TestContainerQualifier(unittest.TestCase):

    def test_no_criteria_always_qualifies(self):
        q = ContainerQualifier()
        self.assertTrue(q.check_if_qualifies(_load()))

    def test_pattern_match_pass(self):
        q = ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))
        self.assertTrue(q.check_if_qualifies(_load(id='L1')))

    def test_pattern_match_fail(self):
        q = ContainerQualifier(pattern=PatternMatchQualifier(regex='^Z'))
        self.assertFalse(q.check_if_qualifies(_load(id='L1')))

    def test_max_dims_qualifies_when_smaller(self):
        q = ContainerQualifier(max_dims=(2.0, 2.0, 2.0))
        self.assertTrue(q.check_if_qualifies(_load(uom=EA)))  # EA dims = (1,1,1)

    def test_max_dims_disqualifies_when_larger(self):
        q = ContainerQualifier(max_dims=(0.5, 0.5, 0.5))
        self.assertFalse(q.check_if_qualifies(_load(uom=EA)))  # EA dims = (1,1,1)

    def test_min_dims_qualifies_when_larger(self):
        q = ContainerQualifier(min_dims=(0.5, 0.5, 0.5))
        self.assertTrue(q.check_if_qualifies(_load(uom=EA)))  # EA dims = (1,1,1)

    def test_min_dims_disqualifies_when_smaller(self):
        q = ContainerQualifier(min_dims=(2.0, 2.0, 2.0))
        self.assertFalse(q.check_if_qualifies(_load(uom=EA)))  # EA dims = (1,1,1)

    def test_combined_criteria(self):
        q = ContainerQualifier(
            pattern=PatternMatchQualifier(regex='^L'),
            max_dims=(2.0, 2.0, 2.0),
            min_dims=(0.5, 0.5, 0.5),
        )
        self.assertTrue(q.check_if_qualifies(_load(id='L1', uom=EA)))

    def test_combined_criteria_fails_on_pattern(self):
        q = ContainerQualifier(
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
        loc.store_containers(['L1'])  # 4 available
        q = LocationQualifier(at_least_capacity=4)
        self.assertTrue(q.check_if_qualifies(loc))

    def test_at_least_capacity_fail(self):
        loc = _loc(capacity=3)
        loc.store_containers(['L1', 'L2'])  # 1 available
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

    def _make_container_provider(self, containers):
        """Build a ContainerByIdProvider backed by a simple dict of Container objects."""
        container_map = {c.id: c for c in containers}
        return lambda ids: {i: container_map[i] for i in ids if i in container_map}

    def test_any_loads_qualifier_pass(self):
        """Location qualifies if at least one container matches any_containers qualifier."""
        loc = _loc(capacity=5)
        loc.store_containers(['L1'])
        provider = self._make_container_provider([dcs.Container(id='L1')])
        q = LocationQualifier(
            any_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertTrue(q.check_if_qualifies(loc, container_provider=provider))

    def test_any_loads_qualifier_fail(self):
        """Location fails if no containers match any_containers qualifier."""
        loc = _loc(capacity=5)
        loc.store_containers(['X1'])
        provider = self._make_container_provider([dcs.Container(id='X1')])
        q = LocationQualifier(
            any_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertFalse(q.check_if_qualifies(loc, container_provider=provider))

    def test_all_loads_qualifier_pass(self):
        """Location qualifies if all containers match all_containers qualifier."""
        loc = _loc(capacity=5)
        loc.store_containers(['L1', 'L2'])
        provider = self._make_container_provider([dcs.Container(id='L1'), dcs.Container(id='L2')])
        q = LocationQualifier(
            all_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertTrue(q.check_if_qualifies(loc, container_provider=provider))

    def test_all_loads_qualifier_fail(self):
        """Location fails if any container doesn't match all_containers qualifier."""
        loc = _loc(capacity=5)
        loc.store_containers(['L1', 'X1'])
        provider = self._make_container_provider([dcs.Container(id='L1'), dcs.Container(id='X1')])
        q = LocationQualifier(
            all_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertFalse(q.check_if_qualifies(loc, container_provider=provider))

    def test_any_loads_without_provider_raises(self):
        """any_containers qualifier without a load_provider should raise."""
        loc = _loc(capacity=5)
        loc.store_containers(['L1'])
        q = LocationQualifier(
            any_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        with self.assertRaises(ValueError):
            q.check_if_qualifies(loc)

    def test_combined_criteria(self):
        loc = _loc(id='A', capacity=5, dims=(10.0, 10.0, 10.0))
        loc.store_containers(['L1'])
        q = LocationQualifier(
            id_pattern=PatternMatchQualifier(regex='^A'),
            at_least_capacity=2,
            reserved=False,
        )
        self.assertTrue(q.check_if_qualifies(loc))


class TestLocationQualifierIsOccupied(unittest.TestCase):

    def _provider(self, containers):
        return lambda ids: {c.id: c for c in containers if c.id in ids}

    def test_is_occupied_true_passes_when_has_container(self):
        loc = _loc(id='A', capacity=3)
        loc = loc.store_containers(['C1'])
        q = LocationQualifier(is_occupied=True)
        self.assertTrue(q.check_if_qualifies(loc))

    def test_is_occupied_true_fails_when_empty(self):
        loc = _loc(id='A', capacity=3)
        q = LocationQualifier(is_occupied=True)
        self.assertFalse(q.check_if_qualifies(loc))

    def test_is_occupied_false_passes_when_empty(self):
        loc = _loc(id='A', capacity=3)
        q = LocationQualifier(is_occupied=False)
        self.assertTrue(q.check_if_qualifies(loc))

    def test_is_occupied_false_fails_when_has_container(self):
        loc = _loc(id='A', capacity=3)
        loc = loc.store_containers(['C1'])
        q = LocationQualifier(is_occupied=False)
        self.assertFalse(q.check_if_qualifies(loc))


class TestLocationQualifierHasContent(unittest.TestCase):

    EACH = dcs.UnitOfMeasure(name='EA')
    SKU_A = dcs.Resource(name='SKU_A')
    SKU_B = dcs.Resource(name='SKU_B')

    def _make_container(self, cid, qty, resource=None, uom=None):
        resource = resource or self.SKU_A
        uom = uom or self.EACH
        contents = frozenset([dcs.ContainerContent(resource=resource, uom=uom, qty=qty)])
        return dcs.Container(id=cid, contents=contents)

    def _provider(self, *containers):
        m = {c.id: c for c in containers}
        return lambda ids: {k: v for k, v in m.items() if k in ids}

    def test_has_content_qualifies_when_sufficient_qty(self):
        c = self._make_container('C1', qty=10.0)
        loc = _loc(id='A', capacity=3)
        loc = loc.store_containers(['C1'])
        q = LocationQualifier(has_content=dcs.ContainerContent(resource=self.SKU_A, uom=self.EACH, qty=5.0))
        self.assertTrue(q.check_if_qualifies(loc, container_provider=self._provider(c)))

    def test_has_content_disqualifies_when_insufficient_qty(self):
        c = self._make_container('C1', qty=2.0)
        loc = _loc(id='A', capacity=3)
        loc = loc.store_containers(['C1'])
        q = LocationQualifier(has_content=dcs.ContainerContent(resource=self.SKU_A, uom=self.EACH, qty=5.0))
        self.assertFalse(q.check_if_qualifies(loc, container_provider=self._provider(c)))

    def test_has_content_aggregates_across_containers(self):
        c1 = self._make_container('C1', qty=3.0)
        c2 = self._make_container('C2', qty=4.0)
        loc = _loc(id='A', capacity=3)
        loc = loc.store_containers(['C1', 'C2'])
        q = LocationQualifier(has_content=dcs.ContainerContent(resource=self.SKU_A, uom=self.EACH, qty=6.0))
        self.assertTrue(q.check_if_qualifies(loc, container_provider=self._provider(c1, c2)))

    def test_has_content_wrong_resource_disqualifies(self):
        c = self._make_container('C1', qty=10.0, resource=self.SKU_B)
        loc = _loc(id='A', capacity=3)
        loc = loc.store_containers(['C1'])
        q = LocationQualifier(has_content=dcs.ContainerContent(resource=self.SKU_A, uom=self.EACH, qty=1.0))
        self.assertFalse(q.check_if_qualifies(loc, container_provider=self._provider(c)))

    def test_has_content_requires_container_provider(self):
        loc = _loc(id='A', capacity=3)
        loc = loc.store_containers(['C1'])
        q = LocationQualifier(has_content=dcs.ContainerContent(resource=self.SKU_A, uom=self.EACH, qty=1.0))
        with self.assertRaises(ValueError):
            q.check_if_qualifies(loc)


if __name__ == "__main__":
    unittest.main()
