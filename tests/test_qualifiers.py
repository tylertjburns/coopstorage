"""
Tests for qualifiers.py

Covers:
- ContainerQualifier: pattern, max_dims, min_dims
- LocationQualifier: id_pattern, max_dims, min_dims, any_loads, all_loads,
                     at_least_capacity, reserved
"""
import unittest
import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.channel_processors as cps
from coopstorage.storage.loc_load.location import Location
from coopstorage.storage.loc_load.qualifiers import ContainerQualifier, LocationQualifier
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
        q = LocationQualifier(reserved=True)
        self.assertTrue(q.check_if_qualifies(loc, is_reserved=lambda _: True))

    def test_reserved_filter_false(self):
        loc = _loc()
        q = LocationQualifier(reserved=False)
        self.assertTrue(q.check_if_qualifies(loc, is_reserved=lambda _: False))

    def test_reserved_filter_excludes_reserved(self):
        loc = _loc()
        q = LocationQualifier(reserved=False)
        self.assertFalse(q.check_if_qualifies(loc, is_reserved=lambda _: True))

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
        """Location qualifies if at least one container matches has_any_containers qualifier."""
        loc = _loc(capacity=5)
        loc.store_containers(['L1'])
        provider = self._make_container_provider([dcs.Container(id='L1')])
        q = LocationQualifier(
            has_any_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertTrue(q.check_if_qualifies(loc, container_provider=provider))

    def test_any_loads_qualifier_fail(self):
        """Location fails if no containers match has_any_containers qualifier."""
        loc = _loc(capacity=5)
        loc.store_containers(['X1'])
        provider = self._make_container_provider([dcs.Container(id='X1')])
        q = LocationQualifier(
            has_any_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertFalse(q.check_if_qualifies(loc, container_provider=provider))

    def test_has_all_containers_single_qualifier_passes_when_one_matches(self):
        """has_all_containers=[q]: qualifies if at least one container satisfies q."""
        loc = _loc(capacity=5)
        loc.store_containers(['L1', 'L2'])
        provider = self._make_container_provider([dcs.Container(id='L1'), dcs.Container(id='L2')])
        q = LocationQualifier(
            has_all_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertTrue(q.check_if_qualifies(loc, container_provider=provider))

    def test_has_all_containers_single_qualifier_passes_with_other_containers_present(self):
        """has_all_containers=[q]: extra containers that don't match q must not cause failure.

        Regression: old (buggy) code checked ALL containers against q, so having
        an X-prefixed container alongside an L-prefixed one caused a false failure.
        """
        loc = _loc(capacity=5)
        loc.store_containers(['L1', 'X1', 'X2'])
        provider = self._make_container_provider([
            dcs.Container(id='L1'), dcs.Container(id='X1'), dcs.Container(id='X2'),
        ])
        q = LocationQualifier(
            has_all_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertTrue(q.check_if_qualifies(loc, container_provider=provider))

    def test_has_all_containers_single_qualifier_fails_when_none_match(self):
        """has_all_containers=[q]: fails only if no container in the location satisfies q."""
        loc = _loc(capacity=5)
        loc.store_containers(['X1', 'X2'])
        provider = self._make_container_provider([dcs.Container(id='X1'), dcs.Container(id='X2')])
        q = LocationQualifier(
            has_all_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertFalse(q.check_if_qualifies(loc, container_provider=provider))

    def test_has_all_containers_empty_location_fails(self):
        """has_all_containers: an empty location must not qualify (no vacuous truth).

        Regression: old code used all(...) over an empty iterable which evaluates
        True, causing empty locations to be incorrectly selected as sources.
        """
        loc = _loc(capacity=5)   # no containers stored
        provider = self._make_container_provider([])
        q = LocationQualifier(
            has_all_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
        )
        self.assertFalse(q.check_if_qualifies(loc, container_provider=provider))

    def test_has_all_containers_multiple_qualifiers_all_satisfied(self):
        """has_all_containers=[q1, q2]: passes when each qualifier is met by at least one container."""
        loc = _loc(capacity=5)
        loc.store_containers(['L1', 'M1'])
        provider = self._make_container_provider([dcs.Container(id='L1'), dcs.Container(id='M1')])
        q = LocationQualifier(
            has_all_containers=[
                ContainerQualifier(pattern=PatternMatchQualifier(regex='^L')),
                ContainerQualifier(pattern=PatternMatchQualifier(regex='^M')),
            ]
        )
        self.assertTrue(q.check_if_qualifies(loc, container_provider=provider))

    def test_has_all_containers_multiple_qualifiers_one_unsatisfied(self):
        """has_all_containers=[q1, q2]: fails if any qualifier has no matching container."""
        loc = _loc(capacity=5)
        loc.store_containers(['L1'])   # no M-prefixed container
        provider = self._make_container_provider([dcs.Container(id='L1')])
        q = LocationQualifier(
            has_all_containers=[
                ContainerQualifier(pattern=PatternMatchQualifier(regex='^L')),
                ContainerQualifier(pattern=PatternMatchQualifier(regex='^M')),
            ]
        )
        self.assertFalse(q.check_if_qualifies(loc, container_provider=provider))

    def test_any_loads_without_provider_raises(self):
        """has_any_containers qualifier without a load_provider should raise."""
        loc = _loc(capacity=5)
        loc.store_containers(['L1'])
        q = LocationQualifier(
            has_any_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))]
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
        self.assertTrue(q.check_if_qualifies(loc, is_reserved=lambda _: False))


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


class TestLocationQualifierSlotFit(unittest.TestCase):
    """Container dims are checked against loc.SlotDims when a container is passed."""

    def _loc_with_axis(self, capacity, dims, channel_axis=0):
        return Location(
            id='A',
            location_meta=dcs.LocationMeta(
                dims=dims,
                channel_processor=cps.AllAvailableChannelProcessor(),
                capacity=capacity,
                channel_axis=channel_axis,
            ),
            coords=(0, 0, 0),
        )

    def test_no_container_always_passes(self):
        """Without a container, slot fit is not checked."""
        loc = self._loc_with_axis(capacity=5, dims=(10.0, 10.0, 10.0))
        # slot_dims = (2, 10, 10); no container provided → passes regardless
        q = LocationQualifier()
        self.assertTrue(q.check_if_qualifies(loc, container=None))

    def test_container_fits_in_slot_passes(self):
        """Container whose dims are <= slot_dims qualifies."""
        loc = self._loc_with_axis(capacity=5, dims=(10.0, 10.0, 10.0))
        # slot_dims along axis 0 = 10/5 = 2; other axes = 10
        small = dcs.Container(id='S', uom=dcs.UnitOfMeasure(name='EA', dimensions=(1.0, 5.0, 5.0)))
        q = LocationQualifier()
        self.assertTrue(q.check_if_qualifies(loc, container=small))

    def test_container_exactly_slot_size_passes(self):
        """Container whose dims exactly match slot_dims qualifies (boundary condition)."""
        loc = self._loc_with_axis(capacity=5, dims=(10.0, 10.0, 10.0))
        # slot_dims = (2, 10, 10)
        exact = dcs.Container(id='E', uom=dcs.UnitOfMeasure(name='EA', dimensions=(2.0, 10.0, 10.0)))
        q = LocationQualifier()
        self.assertTrue(q.check_if_qualifies(loc, container=exact))

    def test_container_too_wide_for_slot_fails(self):
        """Container whose axis-0 dim exceeds slot_dims[0] disqualifies."""
        loc = self._loc_with_axis(capacity=5, dims=(10.0, 10.0, 10.0))
        # slot_dims along axis 0 = 2; container needs 3
        too_wide = dcs.Container(id='W', uom=dcs.UnitOfMeasure(name='EA', dimensions=(3.0, 5.0, 5.0)))
        q = LocationQualifier()
        self.assertFalse(q.check_if_qualifies(loc, container=too_wide))

    def test_container_too_tall_for_slot_fails(self):
        """Container oversized on a non-channel axis also disqualifies."""
        loc = self._loc_with_axis(capacity=5, dims=(10.0, 10.0, 10.0))
        # slot_dims = (2, 10, 10); container is fine on axis 0 but too tall on axis 2
        too_tall = dcs.Container(id='T', uom=dcs.UnitOfMeasure(name='EA', dimensions=(1.0, 5.0, 11.0)))
        q = LocationQualifier()
        self.assertFalse(q.check_if_qualifies(loc, container=too_tall))

    def test_slot_fit_checked_along_correct_axis(self):
        """channel_axis=1 means slots are divided along Y; X and Z fill the full location."""
        loc = self._loc_with_axis(capacity=2, dims=(10.0, 8.0, 10.0), channel_axis=1)
        # slot_dims = (10, 4, 10)
        fits = dcs.Container(id='F', uom=dcs.UnitOfMeasure(name='EA', dimensions=(5.0, 4.0, 5.0)))
        self.assertTrue(LocationQualifier().check_if_qualifies(loc, container=fits))

        too_deep = dcs.Container(id='D', uom=dcs.UnitOfMeasure(name='EA', dimensions=(5.0, 5.0, 5.0)))
        self.assertFalse(LocationQualifier().check_if_qualifies(loc, container=too_deep))

    def test_slot_fit_combined_with_other_criteria(self):
        """Slot fit check composes with other qualifier criteria (all must pass)."""
        loc = self._loc_with_axis(capacity=5, dims=(10.0, 10.0, 10.0))
        # slot_dims = (2, 10, 10); container fits in slot but id_pattern won't match
        small = dcs.Container(id='S', uom=dcs.UnitOfMeasure(name='EA', dimensions=(1.0, 1.0, 1.0)))
        from cooptools.qualifiers import PatternMatchQualifier
        q = LocationQualifier(id_pattern=PatternMatchQualifier(regex='^Z'))
        self.assertFalse(q.check_if_qualifies(loc, container=small))


class TestStorageResolveSourceContainerDest(unittest.TestCase):
    """
    Tests for the reordered resolve_transfer_request_criteria logic:
    - source_only → container inferred from source
    - container_only → source inferred from where container lives
    - both → validate together; error if container not at source
    - new_container → no source, dest selected with slot-fit
    - dest is always resolved last; slot fit enforced via container dims
    """

    def _storage(self, **loc_kwargs):
        """Storage with locations A and B, each capacity=5, dims=(10,10,10)."""
        from coopstorage.storage.loc_load.storage import Storage
        from coopstorage.storage.loc_load.location import Location

        def _make_loc(lid, dims=(10.0, 10.0, 10.0), capacity=5):
            return Location(
                id=lid,
                location_meta=dcs.LocationMeta(
                    dims=dims,
                    channel_processor=cps.AllAvailableChannelProcessor(),
                    capacity=capacity,
                ),
                coords=(0, 0, 0),
            )

        s = Storage()
        s.register_locs([_make_loc('A'), _make_loc('B')])
        return s

    def _seed(self, storage, container_id='C1', loc_id='A'):
        """Place a container at loc_id."""
        from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria
        storage.handle_transfer_requests([
            TransferRequestCriteria(
                new_container=dcs.Container(id=container_id),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex=f'^{loc_id}$')
                ),
            )
        ])

    def test_source_only_infers_container(self):
        """source_loc_query_args alone: container inferred from whatever is at source."""
        from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria
        s = self._storage()
        self._seed(s, 'C1', 'A')

        s.handle_transfer_requests([
            TransferRequestCriteria(
                source_loc_query_args=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^A$')),
                dest_loc_query_args=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^B$')),
            )
        ])
        locs = s.get_locs()
        self.assertNotIn('C1', locs['A'].ContainerIds)
        self.assertIn('C1', locs['B'].ContainerIds)

    def test_container_only_infers_source(self):
        """container_query_args alone: source inferred from where that container lives."""
        from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria
        s = self._storage()
        self._seed(s, 'C1', 'A')

        s.handle_transfer_requests([
            TransferRequestCriteria(
                container_query_args=ContainerQualifier(
                    pattern=PatternMatchQualifier(regex='^C1$')
                ),
                dest_loc_query_args=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^B$')),
            )
        ])
        locs = s.get_locs()
        self.assertNotIn('C1', locs['A'].ContainerIds)
        self.assertIn('C1', locs['B'].ContainerIds)

    def test_both_source_and_container_consistent(self):
        """When both source and container criteria are given and consistent, transfer succeeds."""
        from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria
        s = self._storage()
        self._seed(s, 'C1', 'A')

        s.handle_transfer_requests([
            TransferRequestCriteria(
                source_loc_query_args=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^A$')),
                container_query_args=ContainerQualifier(pattern=PatternMatchQualifier(regex='^C1$')),
                dest_loc_query_args=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^B$')),
            )
        ])
        locs = s.get_locs()
        self.assertIn('C1', locs['B'].ContainerIds)

    def test_slot_fit_enforced_on_dest_selection(self):
        """Dest is skipped when container dims exceed slot_dims; the fitting location is chosen."""
        from coopstorage.storage.loc_load.storage import Storage
        from coopstorage.storage.loc_load.location import Location
        from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria

        # SMALL: dims=(4,10,10), capacity=2 → slot_dims=(2,10,10)  ← too narrow for BIG container
        # LARGE: dims=(20,10,10), capacity=2 → slot_dims=(10,10,10) ← fits BIG container
        def _loc(lid, dims, capacity=2):
            return Location(
                id=lid,
                location_meta=dcs.LocationMeta(
                    dims=dims,
                    channel_processor=cps.AllAvailableChannelProcessor(),
                    capacity=capacity,
                ),
                coords=(0, 0, 0),
            )

        s = Storage()
        s.register_locs([_loc('SMALL', (4.0, 10.0, 10.0)), _loc('LARGE', (20.0, 10.0, 10.0))])

        big_uom = dcs.UnitOfMeasure(name='PALLET', dimensions=(8.0, 8.0, 8.0))
        big_container = dcs.Container(id='BIG', uom=big_uom)

        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_container=big_container,
                dest_loc_query_args=LocationQualifier(at_least_capacity=1),
            )
        ])
        locs = s.get_locs()
        self.assertNotIn('BIG', locs['SMALL'].ContainerIds)
        self.assertIn('BIG', locs['LARGE'].ContainerIds)

    def test_no_qualifying_dest_raises(self):
        """If container is too large for every available location, NoLocations is raised."""
        from coopstorage.storage.loc_load.storage import Storage
        from coopstorage.storage.loc_load.location import Location
        from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria
        from coopstorage.storage.loc_load.exceptions import NoLocationsMatchFilterCriteriaException

        def _loc(lid):
            return Location(
                id=lid,
                location_meta=dcs.LocationMeta(
                    dims=(4.0, 4.0, 4.0),
                    channel_processor=cps.AllAvailableChannelProcessor(),
                    capacity=2,
                ),
                coords=(0, 0, 0),
            )

        s = Storage()
        s.register_locs([_loc('TINY')])

        # slot_dims = (2, 4, 4); container needs (5, 4, 4) → won't fit anywhere
        huge_uom = dcs.UnitOfMeasure(name='BIG', dimensions=(5.0, 4.0, 4.0))
        huge_container = dcs.Container(id='HUGE', uom=huge_uom)

        with self.assertRaises(NoLocationsMatchFilterCriteriaException):
            s.handle_transfer_requests([
                TransferRequestCriteria(
                    new_container=huge_container,
                    dest_loc_query_args=LocationQualifier(at_least_capacity=1),
                )
            ])


class TestLocationQualifierUomQualifier(unittest.TestCase):
    """Tests for uom_qualifier on LocationMeta — disqualifies containers whose UoM is not allowed."""

    ALLOWED_UOM  = dcs.UnitOfMeasure(name='PALLET', dimensions=(1.0, 1.0, 1.0))
    REJECTED_UOM = dcs.UnitOfMeasure(name='BOX',    dimensions=(1.0, 1.0, 1.0))

    def _loc_with_uom_qualifier(self, allowed_names):
        from cooptools.qualifiers import WhiteBlackListQualifier
        return Location(
            id='A',
            location_meta=dcs.LocationMeta(
                dims=(10.0, 10.0, 10.0),
                channel_processor=cps.AllAvailableChannelProcessor(),
                capacity=5,
                uom_qualifier=WhiteBlackListQualifier(white_list=allowed_names),
            ),
            coords=(0, 0, 0),
        )

    def test_allowed_uom_qualifies(self):
        loc = self._loc_with_uom_qualifier([self.ALLOWED_UOM])
        c = dcs.Container(id='C1', uom=self.ALLOWED_UOM)
        self.assertTrue(LocationQualifier().check_if_qualifies(loc, container=c))

    def test_rejected_uom_disqualifies(self):
        loc = self._loc_with_uom_qualifier([self.ALLOWED_UOM])
        c = dcs.Container(id='C1', uom=self.REJECTED_UOM)
        self.assertFalse(LocationQualifier().check_if_qualifies(loc, container=c))

    def test_ignore_uom_qualifier_bypasses_check(self):
        """ignore_uom_qualifier=True means even a rejected UoM passes."""
        loc = self._loc_with_uom_qualifier([self.ALLOWED_UOM])
        c = dcs.Container(id='C1', uom=self.REJECTED_UOM)
        q = LocationQualifier(ignore_uom_qualifier=True)
        self.assertTrue(q.check_if_qualifies(loc, container=c))

    def test_no_container_skips_uom_check(self):
        """Without a container argument, uom_qualifier is not evaluated."""
        loc = self._loc_with_uom_qualifier([self.ALLOWED_UOM])
        self.assertTrue(LocationQualifier().check_if_qualifies(loc, container=None))

    def test_no_uom_qualifier_on_loc_always_passes(self):
        """When LocationMeta has no uom_qualifier, any container UoM is accepted."""
        loc = _loc()  # no uom_qualifier
        c = dcs.Container(id='C1', uom=self.REJECTED_UOM)
        self.assertTrue(LocationQualifier().check_if_qualifies(loc, container=c))


class TestLocationQualifierResourceTypeQualifier(unittest.TestCase):
    """Tests for resource_type_qualifier on LocationMeta — disqualifies containers whose
    resource types are not all allowed by the location's whitelist."""

    SKU_A = dcs.Resource(name='SKU_A')
    SKU_B = dcs.Resource(name='SKU_B')
    EACH  = dcs.UnitOfMeasure(name='EA')

    def _loc_with_resource_qualifier(self, allowed_resources):
        from cooptools.qualifiers import WhiteBlackListQualifier
        return Location(
            id='A',
            location_meta=dcs.LocationMeta(
                dims=(10.0, 10.0, 10.0),
                channel_processor=cps.AllAvailableChannelProcessor(),
                capacity=5,
                resource_type_qualifier=WhiteBlackListQualifier(white_list=allowed_resources),
            ),
            coords=(0, 0, 0),
        )

    def _container_with_resources(self, cid, *resources):
        contents = frozenset(
            dcs.ContainerContent(resource=r, uom=self.EACH, qty=1.0)
            for r in resources
        )
        return dcs.Container(id=cid, contents=contents)

    def test_allowed_resource_qualifies(self):
        loc = self._loc_with_resource_qualifier([self.SKU_A])
        c = self._container_with_resources('C1', self.SKU_A)
        self.assertTrue(LocationQualifier().check_if_qualifies(loc, container=c))

    def test_rejected_resource_disqualifies(self):
        loc = self._loc_with_resource_qualifier([self.SKU_A])
        c = self._container_with_resources('C1', self.SKU_B)
        self.assertFalse(LocationQualifier().check_if_qualifies(loc, container=c))

    def test_mixed_resources_disqualifies_when_one_rejected(self):
        """Container with both an allowed and a rejected resource type fails."""
        loc = self._loc_with_resource_qualifier([self.SKU_A])
        c = self._container_with_resources('C1', self.SKU_A, self.SKU_B)
        self.assertFalse(LocationQualifier().check_if_qualifies(loc, container=c))

    def test_empty_container_qualifies(self):
        """A container with no contents has no resource types — nothing to reject."""
        loc = self._loc_with_resource_qualifier([self.SKU_A])
        c = dcs.Container(id='C1')  # no contents → ResourceTypes = {}
        self.assertTrue(LocationQualifier().check_if_qualifies(loc, container=c))

    def test_ignore_resource_type_qualifier_bypasses_check(self):
        loc = self._loc_with_resource_qualifier([self.SKU_A])
        c = self._container_with_resources('C1', self.SKU_B)
        q = LocationQualifier(ignore_resource_type_qualifier=True)
        self.assertTrue(q.check_if_qualifies(loc, container=c))

    def test_no_container_skips_resource_type_check(self):
        loc = self._loc_with_resource_qualifier([self.SKU_A])
        self.assertTrue(LocationQualifier().check_if_qualifies(loc, container=None))

    def test_no_resource_type_qualifier_on_loc_always_passes(self):
        loc = _loc()  # no resource_type_qualifier
        c = self._container_with_resources('C1', self.SKU_B)
        self.assertTrue(LocationQualifier().check_if_qualifies(loc, container=c))


if __name__ == "__main__":
    unittest.main()
