"""
Tests for storage.py (Storage class)

Covers:
- register_locs / get_locs
- register_loads / get_loads
- filter with LocationQualifier
- select_location
- select_load
- handle_transfer_requests: all 3 transfer types
  1. new load → dest (no source)
  2. source → dest (move)
  3. source only (remove)
- LoadLocs / LocLoads properties
- from_meta factory
- Thread safety (concurrent writes don't corrupt state)
"""
import threading
import unittest

import coopstorage.storage2.loc_load.channel_processors as cps
import coopstorage.storage2.loc_load.dcs as dcs
from coopstorage.storage2.loc_load.location import Location
from coopstorage.storage2.loc_load.qualifiers import LocationQualifier, LoadQualifier
from coopstorage.storage2.loc_load.storage import Storage
from coopstorage.storage2.loc_load.transferRequest import TransferRequestCriteria
from coopstorage.storage2.loc_load.exceptions import NoLocationsMatchFilterCriteriaException
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
    return dcs.Load(id=load_id)

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
        locs['B'].store_loads(['X'])
        result = s.get_locs(criteria=LocationQualifier(at_least_capacity=2))
        self.assertIn('A', result)
        self.assertNotIn('B', result)

    def test_register_locs_returns_self_for_chaining(self):
        s = Storage()
        result = s.register_locs([_loc('A')])
        self.assertIs(result, s)


# ── register_loads / get_loads ────────────────────────────────────────────────

class TestRegisterAndGetLoads(unittest.TestCase):

    def test_register_single_load(self):
        s = Storage()
        s.register_loads([_load('L1')])
        loads = s.get_loads()
        self.assertIn('L1', loads)

    def test_register_multiple_loads(self):
        s = Storage()
        s.register_loads([_load('L1'), _load('L2'), _load('L3')])
        self.assertEqual(len(s.get_loads()), 3)

    def test_get_loads_with_qualifier(self):
        s = Storage()
        s.register_loads([_load('L1'), _load('X1')])
        result = s.get_loads(
            criteria=LoadQualifier(pattern=PatternMatchQualifier(regex='^L'))
        )
        self.assertIn('L1', result)
        self.assertNotIn('X1', result)

    def test_register_loads_returns_self_for_chaining(self):
        s = Storage()
        result = s.register_loads([_load('L1')])
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


# ── handle_transfer_requests: type 1 (new load → dest) ───────────────────────

class TestTransferType1NewLoadToDest(unittest.TestCase):

    def test_store_new_load_at_specific_dest(self):
        s = _storage_with_locs('A', 'B')
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_load=_load('L1'),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^A')
                ),
            )
        ])
        locs = s.get_locs()
        self.assertIn('L1', locs['A'].LoadIds)

    def test_store_multiple_new_loads(self):
        s = _storage_with_locs('A', 'B', 'C')
        s.handle_transfer_requests([
            TransferRequestCriteria(new_load=_load('L1'), dest_loc_query_args=LocationQualifier(at_least_capacity=1)),
            TransferRequestCriteria(new_load=_load('L2'), dest_loc_query_args=LocationQualifier(at_least_capacity=1)),
            TransferRequestCriteria(new_load=_load('L3'), dest_loc_query_args=LocationQualifier(at_least_capacity=1)),
        ])
        all_load_ids = {l.id for l in s.Loads}
        self.assertEqual(all_load_ids, {'L1', 'L2', 'L3'})

    def test_load_registered_in_data_store(self):
        s = _storage_with_locs('A')
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_load=_load('L1'),
                dest_loc_query_args=LocationQualifier(at_least_capacity=1),
            )
        ])
        self.assertIn('L1', s.get_loads())


# ── handle_transfer_requests: type 2 (source → dest) ─────────────────────────

class TestTransferType2SourceToDest(unittest.TestCase):

    def _setup(self):
        s = _storage_with_locs('SRC', 'DST')
        # Pre-load a load into SRC
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_load=_load('L1'),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^SRC')
                ),
            )
        ])
        return s

    def test_move_load_from_src_to_dst(self):
        s = self._setup()
        s.handle_transfer_requests([
            TransferRequestCriteria(
                load_query_args=LoadQualifier(pattern=PatternMatchQualifier(regex='^L1')),
                source_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^SRC')
                ),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^DST')
                ),
            )
        ])
        locs = s.get_locs()
        self.assertNotIn('L1', locs['SRC'].LoadIds)
        self.assertIn('L1', locs['DST'].LoadIds)

    def test_source_empty_after_move(self):
        s = self._setup()
        s.handle_transfer_requests([
            TransferRequestCriteria(
                load_query_args=LoadQualifier(),
                source_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^SRC')
                ),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^DST')
                ),
            )
        ])
        locs = s.get_locs()
        self.assertEqual(locs['SRC'].LoadIds, [])


# ── handle_transfer_requests: type 3 (remove from source) ────────────────────

class TestTransferType3RemoveOnly(unittest.TestCase):

    def test_remove_load_from_source(self):
        s = _storage_with_locs('A')
        # Put a load in
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_load=_load('L1'),
                dest_loc_query_args=LocationQualifier(at_least_capacity=1),
            )
        ])
        # Remove it
        s.handle_transfer_requests([
            TransferRequestCriteria(
                load_query_args=LoadQualifier(pattern=PatternMatchQualifier(regex='^L1')),
                source_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^A')
                ),
            )
        ])
        locs = s.get_locs()
        self.assertEqual(locs['A'].LoadIds, [])


# ── Properties ────────────────────────────────────────────────────────────────

class TestStorageProperties(unittest.TestCase):

    def _storage_with_load_at_loc(self):
        s = _storage_with_locs('A', 'B')
        s.handle_transfer_requests([
            TransferRequestCriteria(
                new_load=_load('L1'),
                dest_loc_query_args=LocationQualifier(
                    id_pattern=PatternMatchQualifier(regex='^A')
                ),
            )
        ])
        return s

    def test_loads_property(self):
        s = self._storage_with_load_at_loc()
        self.assertEqual(len(s.Loads), 1)
        self.assertEqual(s.Loads[0].id, 'L1')

    def test_locations_property(self):
        s = _storage_with_locs('A', 'B', 'C')
        self.assertEqual(len(s.Locations), 3)

    def test_loc_loads_property(self):
        s = self._storage_with_load_at_loc()
        loc_loads = s.LocLoads
        a_loc = next(loc for loc in loc_loads if loc.Id == 'A')
        loads_at_a = loc_loads[a_loc]
        self.assertEqual(len(loads_at_a), 1)
        self.assertEqual(loads_at_a[0].id, 'L1')

    def test_load_locs_property(self):
        s = self._storage_with_load_at_loc()
        load_locs = s.LoadLocs
        l1 = next(load for load in load_locs if load.id == 'L1')
        self.assertEqual(load_locs[l1].Id, 'A')


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

    def test_concurrent_register_loads(self):
        """Many threads registering loads concurrently should not lose any."""
        s = Storage()
        errors = []

        def register(load_id):
            try:
                s.register_loads([_load(load_id)])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(f'L{i}',)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(s.get_loads()), 50)


if __name__ == "__main__":
    unittest.main()
