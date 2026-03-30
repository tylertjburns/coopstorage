"""
Tests for storage.py (Storage class)

Covers:
- register_locs / get_locs
- register_containers / get_containers
- filter with LocationQualifier
- select_location
- select_container
- handle_transfer_requests: all 3 transfer types
  1. new container → dest (no source)
  2. source → dest (move)
  3. source only (remove)
- ContainerLocs / LocContainers properties
- from_meta factory
- Thread safety (concurrent writes don't corrupt state)
"""
import threading
import unittest

import coopstorage.storage2.loc_load.channel_processors as cps
import coopstorage.storage2.loc_load.dcs as dcs
from coopstorage.storage2.loc_load.location import Location
from coopstorage.storage2.loc_load.qualifiers import LocationQualifier, ContainerQualifier
from coopstorage.storage2.loc_load.storage import Storage
from coopstorage.storage2.loc_load.transferRequest import TransferRequestCriteria
from coopstorage.storage2.loc_load.exceptions import (
    NoLocationsMatchFilterCriteriaException,
    UnexpectedContainerCountException,
)
from coopstorage.storage2.loc_load.dcs import ContainerContent, UnitOfMeasure, Resource
from cooptools.qualifiers import PatternMatchQualifier

# ── helpers ───────────────────────────────────────────────────────────────────

def _meta(capacity=3):
    return dcs.LocationMeta(
        dims=(10, 10, 10),
        channel_processor=cps.AllAvailableChannelProcessor(),
        capacity=capacity,
    )

def _loc(loc_id, capacity=3):
    return Location(id=loc_id, location_meta=_meta(capacity), coords=(0, 0, 0))

def _load(load_id):
    return dcs.Container(id=load_id)

def _storage_with_locs(*loc_ids, capacity=3):
    s = Storage()
    s.register_locs([_loc(i, capacity) for i in loc_ids])
    return s


# ── register_locs / get_locs ──────────────────────────────────────────────────

class TestRegisterAndGetLocs(unittest.TestCase):

    def test_register_single_loc(self):
        s = Storage()
        s.register_locs([_loc('A')])
        locs = s.get_locs()
        self.assertIn('A', locs)

    def test_register_multiple_locs(self):
        s = _storage_with_locs('A', 'B', 'C')
        self.assertEqual(len(s.get_locs()), 3)

    def test_get_locs_with_id_pattern_qualifier(self):
        s = _storage_with_locs('AA', 'AB', 'BC')
        result = s.get_locs(
            criteria=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^A'))
        )
        self.assertEqual(set(result.keys()), {'AA', 'AB'})

    def test_get_locs_with_capacity_qualifier(self):
        s = Storage()
        s.register_locs([_loc('A', capacity=5), _loc('B', capacity=1)])
        # Fill B so it has 0 available
        locs = s.get_locs()
        locs['B'].store_containers(['X'])
        result = s.get_locs(criteria=LocationQualifier(at_least_capacity=2))
        self.assertIn('A', result)
        self.assertNotIn('B', result)

    def test_register_locs_returns_self_for_chaining(self):
        s = Storage()
        result = s.register_locs([_loc('A')])
        self.assertIs(result, s)


# ── register_containers / get_containers ──────────────────────────────────────

class TestRegisterAndGetContainers(unittest.TestCase):

    def test_register_single_container(self):
        s = Storage()
        s.register_containers([_load('L1')])
        containers = s.get_containers()
        self.assertIn('L1', containers)

    def test_register_multiple_containers(self):
        s = Storage()
        s.register_containers([_load('L1'), _load('L2'), _load('L3')])
        self.assertEqual(len(s.get_containers()), 3)

    def test_get_containers_with_qualifier(self):
        s = Storage()
        s.register_containers([_load('L1'), _load('X1')])
        result = s.get_containers(
            criteria=ContainerQualifier(pattern=PatternMatchQualifier(regex='^L'))
        )
        self.assertIn('L1', result)
        self.assertNotIn('X1', result)

    def test_register_containers_returns_self_for_chaining(self):
        s = Storage()
        result = s.register_containers([_load('L1')])
        self.assertIs(result, s)


# ── filter / select_location ──────────────────────────────────────────────────

class TestSelectLocation(unittest.TestCase):

    def test_filter_returns_all_when_no_criteria(self):
        s = _storage_with_locs('A', 'B', 'C')
        result = s.filter()
        self.assertEqual(len(result), 3)

    def test_filter_by_qualifier(self):
        s = _storage_with_locs('A', 'B', 'C')
        result = s.filter(filter=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^A')))
        self.assertEqual(len(result), 1)

    def test_select_location_returns_one(self):
        s = _storage_with_locs('A', 'B')
        loc = s.select_location()
        self.assertIn(loc.Id, ['A', 'B'])

    def test_select_location_with_qualifier(self):
        s = _storage_with_locs('A', 'B', 'C')
        loc = s.select_location(
            filter=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^B'))
        )
        self.assertEqual(loc.Id, 'B')

    def test_select_location_no_match_raises(self):
        s = _storage_with_locs('A', 'B')
        with self.assertRaises(NoLocationsMatchFilterCriteriaException):
            s.select_location(
                filter=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^Z'))
            )


# ── handle_transfer_requests: type 1 (new container → dest) ──────────────────

class TestTransferType1NewContainerToDest(unittest.TestCase):

    def test_store_new_container_at_specific_dest(self):
        s = _storage_with_locs('A', 'B')
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_container=_load('L1'),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^A')
                ),
            )
        ])
        locs = s.get_locs()
        self.assertIn('L1', locs['A'].ContainerIds)

    def test_store_multiple_new_containers(self):
        s = _storage_with_locs('A', 'B', 'C')
        s.handle_transfer_requests([
            TransferRequestCriteria(new_container=_load('L1'), dest_loc_query_args=LocationQualifier(at_least_capacity=1)),
            TransferRequestCriteria(new_container=_load('L2'), dest_loc_query_args=LocationQualifier(at_least_capacity=1)),
            TransferRequestCriteria(new_container=_load('L3'), dest_loc_query_args=LocationQualifier(at_least_capacity=1)),
        ])
        all_container_ids = {l.id for l in s.Containers}
        self.assertEqual(all_container_ids, {'L1', 'L2', 'L3'})

    def test_container_registered_in_data_store(self):
        s = _storage_with_locs('A')
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_container=_load('L1'),
                dest_loc_query_args=LocationQualifier(at_least_capacity=1),
            )
        ])
        self.assertIn('L1', s.get_containers())


# ── handle_transfer_requests: type 2 (source → dest) ─────────────────────────

class TestTransferType2SourceToDest(unittest.TestCase):

    def _setup(self):
        s = _storage_with_locs('SRC', 'DST')
        # Pre-load a container into SRC
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_container=_load('L1'),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^SRC')
                ),
            )
        ])
        return s

    def test_move_container_from_src_to_dst(self):
        s = self._setup()
        s.handle_transfer_requests([
            TransferRequestCriteria(
                container_query_args=ContainerQualifier(pattern=PatternMatchQualifier(regex='^L1')),
                source_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^SRC')
                ),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^DST')
                ),
            )
        ])
        locs = s.get_locs()
        self.assertNotIn('L1', locs['SRC'].ContainerIds)
        self.assertIn('L1', locs['DST'].ContainerIds)

    def test_source_empty_after_move(self):
        s = self._setup()
        s.handle_transfer_requests([
            TransferRequestCriteria(
                container_query_args=ContainerQualifier(),
                source_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^SRC')
                ),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^DST')
                ),
            )
        ])
        locs = s.get_locs()
        self.assertEqual(locs['SRC'].ContainerIds, [])


# ── handle_transfer_requests: type 3 (remove from source) ────────────────────

class TestTransferType3RemoveOnly(unittest.TestCase):

    def test_remove_container_from_source(self):
        s = _storage_with_locs('A')
        # Put a container in
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_container=_load('L1'),
                dest_loc_query_args=LocationQualifier(at_least_capacity=1),
            )
        ])
        # Remove it
        s.handle_transfer_requests([
            TransferRequestCriteria(
                container_query_args=ContainerQualifier(pattern=PatternMatchQualifier(regex='^L1')),
                source_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^A')
                ),
            )
        ])
        locs = s.get_locs()
        self.assertEqual(locs['A'].ContainerIds, [])


# ── Properties ────────────────────────────────────────────────────────────────

class TestStorageProperties(unittest.TestCase):

    def _storage_with_container_at_loc(self):
        s = _storage_with_locs('A', 'B')
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_container=_load('L1'),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^A')
                ),
            )
        ])
        return s

    def test_containers_property(self):
        s = self._storage_with_container_at_loc()
        self.assertEqual(len(s.Containers), 1)
        self.assertEqual(s.Containers[0].id, 'L1')

    def test_locations_property(self):
        s = _storage_with_locs('A', 'B', 'C')
        self.assertEqual(len(s.Locations), 3)

    def test_loc_containers_property(self):
        s = self._storage_with_container_at_loc()
        loc_containers = s.LocContainers
        a_loc = next(loc for loc in loc_containers if loc.Id == 'A')
        containers_at_a = loc_containers[a_loc]
        self.assertEqual(len(containers_at_a), 1)
        self.assertEqual(containers_at_a[0].id, 'L1')

    def test_container_locs_property(self):
        s = self._storage_with_container_at_loc()
        container_locs = s.ContainerLocs
        l1 = next(container for container in container_locs if container.id == 'L1')
        self.assertEqual(container_locs[l1].Id, 'A')


# ── from_meta factory ─────────────────────────────────────────────────────────

class TestFromMeta(unittest.TestCase):

    def test_creates_correct_number_of_locs(self):
        s = Storage.from_meta(
            location_type_counts=[(_meta(capacity=5), 4)],
            naming_provider=lambda x: f"LOC-{x}",
        )
        self.assertEqual(len(s.get_locs()), 4)

    def test_naming_provider_applied(self):
        s = Storage.from_meta(
            location_type_counts=[(_meta(), 3)],
            naming_provider=lambda x: f"RACK-{x:02d}",
        )
        locs = s.get_locs()
        self.assertIn('RACK-00', locs)
        self.assertIn('RACK-01', locs)
        self.assertIn('RACK-02', locs)

    def test_mixed_meta_types(self):
        fifo_meta = dcs.LocationMeta(
            dims=(10, 10, 10),
            channel_processor=cps.FIFOFlowChannelProcessor(),
            capacity=5,
        )
        lifo_meta = dcs.LocationMeta(
            dims=(5, 5, 5),
            channel_processor=cps.LIFOFlowChannelProcessor(),
            capacity=2,
        )
        idx = [0]
        def namer(x):
            idx[0] += 1
            return f"LOC-{idx[0]}"

        s = Storage.from_meta(
            location_type_counts=[(fifo_meta, 3), (lifo_meta, 2)],
            naming_provider=namer,
        )
        self.assertEqual(len(s.get_locs()), 5)


# ── Thread safety ─────────────────────────────────────────────────────────────

class TestThreadSafety(unittest.TestCase):

    def test_concurrent_register_containers(self):
        """Many threads registering containers concurrently should not lose any."""
        s = Storage()
        errors = []

        def register(load_id):
            try:
                s.register_containers([_load(load_id)])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(f'L{i}',)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(s.get_containers()), 50)


# ── add/remove content at location ────────────────────────────────────────────

EACH = UnitOfMeasure(name="EA")
SKU_A = Resource(name="SKU_A")
SKU_B = Resource(name="SKU_B")

def _content(resource=None, uom=None, qty=1.0):
    return ContainerContent(resource=resource or SKU_A, uom=uom or EACH, qty=qty)

def _bulk_storage(loc_id='BIN'):
    """One location with capacity=1, one permanent container already stored."""
    s = Storage()
    s.register_locs([_loc(loc_id, capacity=1)])
    s.register_containers([_load('C1')])
    s.handle_transfer_requests([
        TransferRequestCriteria(
            new_container=_load('C1'),
            dest_loc_query_args=LocationQualifier(at_least_capacity=1)
        )
    ])
    return s


class TestInventoryAggregation(unittest.TestCase):

    def _seeded_storage(self):
        """Two locations: BIN1 (occupied), BIN2 (empty)."""
        s = Storage()
        s.register_locs([_loc('BIN1', capacity=1), _loc('BIN2', capacity=1)])
        s.register_containers([_load('C1')])
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_container=_load('C1'),
                dest_loc_query_args=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^BIN1$'))
            )
        ])
        return s

    def test_occupied_locs(self):
        s = self._seeded_storage()
        occupied = s.OccupiedLocs
        self.assertEqual(len(occupied), 1)
        self.assertEqual(occupied[0].Id, 'BIN1')

    def test_empty_locs(self):
        s = self._seeded_storage()
        empty = s.EmptyLocs
        self.assertEqual(len(empty), 1)
        self.assertEqual(empty[0].Id, 'BIN2')

    def test_content_at_location_aggregates(self):
        s = Storage()
        s.register_locs([_loc('BIN1', capacity=2)])
        # Place a container with content at BIN1
        container = dcs.Container(
            id='C1',
            contents=frozenset([ContainerContent(resource=SKU_A, uom=EACH, qty=5.0)])
        )
        s.register_containers([container])
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_container=container,
                dest_loc_query_args=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^BIN1$'))
            )
        ])
        contents = s.content_at_location('BIN1')
        total = sum(c.qty for c in contents)
        self.assertAlmostEqual(total, 5.0)

    def test_content_at_location_empty_returns_empty(self):
        s = Storage()
        s.register_locs([_loc('BIN1', capacity=1)])
        self.assertEqual(s.content_at_location('BIN1'), [])

    def test_inventory_by_resource_uom(self):
        s = Storage()
        s.register_locs([_loc('BIN1', capacity=2), _loc('BIN2', capacity=2)])
        c1 = dcs.Container(id='C1', contents=frozenset([ContainerContent(resource=SKU_A, uom=EACH, qty=3.0)]))
        c2 = dcs.Container(id='C2', contents=frozenset([ContainerContent(resource=SKU_A, uom=EACH, qty=4.0)]))
        s.register_containers([c1, c2])
        s.handle_transfer_requests([
            TransferRequestCriteria(new_container=c1, dest_loc_query_args=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^BIN1$'))),
            TransferRequestCriteria(new_container=c2, dest_loc_query_args=LocationQualifier(id_pattern=PatternMatchQualifier(regex='^BIN2$'))),
        ])
        inv = s.InventoryByResourceUom
        self.assertAlmostEqual(inv[(SKU_A, EACH)], 7.0)

    def test_inventory_by_resource_uom_empty(self):
        s = Storage()
        self.assertEqual(s.InventoryByResourceUom, {})


class TestAddContentAtLocation(unittest.TestCase):

    def test_add_content_increases_qty(self):
        s = _bulk_storage()
        s.add_content_to_container_at_location('BIN', [_content(qty=5.0)])
        container = list(s.get_containers().values())[0]
        total = sum(c.qty for c in container.contents)
        self.assertAlmostEqual(total, 5.0)

    def test_add_content_twice_merges(self):
        s = _bulk_storage()
        s.add_content_to_container_at_location('BIN', [_content(qty=3.0)])
        s.add_content_to_container_at_location('BIN', [_content(qty=4.0)])
        container = list(s.get_containers().values())[0]
        total = sum(c.qty for c in container.contents)
        self.assertAlmostEqual(total, 7.0)

    def test_add_content_unknown_loc_raises(self):
        s = _bulk_storage()
        with self.assertRaises(Exception):
            s.add_content_to_container_at_location('NOPE', [_content(qty=1.0)])

    def test_add_content_empty_loc_raises(self):
        s = Storage()
        s.register_locs([_loc('EMPTY', capacity=1)])
        with self.assertRaises(UnexpectedContainerCountException):
            s.add_content_to_container_at_location('EMPTY', [_content(qty=1.0)])


class TestRemoveContentAtLocation(unittest.TestCase):

    def _seeded(self, qty=10.0):
        s = _bulk_storage()
        s.add_content_to_container_at_location('BIN', [_content(qty=qty)])
        return s

    def test_remove_content_decreases_qty(self):
        s = self._seeded(10.0)
        s.remove_content_from_container_at_location('BIN', _content(qty=3.0))
        container = list(s.get_containers().values())[0]
        total = sum(c.qty for c in container.contents)
        self.assertAlmostEqual(total, 7.0)

    def test_remove_all_content_empties_container(self):
        s = self._seeded(5.0)
        s.remove_content_from_container_at_location('BIN', _content(qty=5.0))
        container = list(s.get_containers().values())[0]
        self.assertEqual(len(container.contents), 0)

    def test_remove_more_than_available_raises(self):
        s = self._seeded(3.0)
        with self.assertRaises(ValueError):
            s.remove_content_from_container_at_location('BIN', _content(qty=10.0))

    def test_remove_content_empty_loc_raises(self):
        s = Storage()
        s.register_locs([_loc('EMPTY', capacity=1)])
        with self.assertRaises(UnexpectedContainerCountException):
            s.remove_content_from_container_at_location('EMPTY', _content(qty=1.0))


if __name__ == "__main__":
    unittest.main()
