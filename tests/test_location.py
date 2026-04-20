"""
Tests for location.py

Covers:
- Location creation and basic properties
- store_containers / remove_containers
- Capacity and AvailableCapacity
- Reservation system
- FIFO/LIFO access rules via channel processor
- to_jsonable_dict / from_jsonable_dict round-trip
"""
import unittest

import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.channel_processors as cps
from coopstorage.storage.loc_load.location import Location
from coopstorage.storage.loc_load.channel_processors import (
    ItemNotAccessibleToRemoveException,
    NoRoomToAddException,
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _fifo_loc(capacity=3, loc_id='LOC-A'):
    return Location(
        id=loc_id,
        location_meta=dcs.LocationMeta(
            dims=(10, 10, 10),
            channel_processor=cps.FIFOFlowChannelProcessor(),
            capacity=capacity,
        ),
        coords=(0, 0, 0),
    )

def _lifo_loc(capacity=3, loc_id='LOC-B'):
    return Location(
        id=loc_id,
        location_meta=dcs.LocationMeta(
            dims=(10, 10, 10),
            channel_processor=cps.LIFOFlowChannelProcessor(),
            capacity=capacity,
        ),
        coords=(0, 0, 0),
    )

def _all_avail_loc(capacity=5, loc_id='LOC-C'):
    return Location(
        id=loc_id,
        location_meta=dcs.LocationMeta(
            dims=(10, 10, 10),
            channel_processor=cps.AllAvailableChannelProcessor(),
            capacity=capacity,
        ),
        coords=(0, 0, 0),
    )


# ── Creation ──────────────────────────────────────────────────────────────────

class TestLocationCreation(unittest.TestCase):

    def test_id_and_meta(self):
        loc = _fifo_loc(capacity=5, loc_id='X')
        self.assertEqual(loc.Id, 'X')
        self.assertEqual(loc.Capacity, 5)

    def test_starts_empty(self):
        loc = _fifo_loc()
        self.assertEqual(loc.ContainerIds, [])
        self.assertEqual(loc.AvailableCapacity, 3)


# ── store_containers ───────────────────────────────────────────────────────────────

class TestStoreLoads(unittest.TestCase):

    def test_store_single_load(self):
        loc = _fifo_loc()
        loc.store_containers(['L1'])
        self.assertIn('L1', loc.ContainerIds)

    def test_store_multiple_loads(self):
        loc = _all_avail_loc(capacity=5)
        loc.store_containers(['L1', 'L2', 'L3'])
        self.assertEqual(set(loc.ContainerIds), {'L1', 'L2', 'L3'})

    def test_available_capacity_decreases(self):
        loc = _fifo_loc(capacity=3)
        loc.store_containers(['L1'])
        self.assertEqual(loc.AvailableCapacity, 2)

    def test_store_at_capacity_raises(self):
        loc = _fifo_loc(capacity=2)
        loc.store_containers(['L1', 'L2'])
        with self.assertRaises(NoRoomToAddException):
            loc.store_containers(['L3'])


# ── remove_containers ──────────────────────────────────────────────────────────────

class TestRemoveLoads(unittest.TestCase):

    def test_remove_load(self):
        loc = _all_avail_loc()
        loc.store_containers(['L1', 'L2'])
        loc.remove_containers(['L1'])
        self.assertNotIn('L1', loc.ContainerIds)
        self.assertIn('L2', loc.ContainerIds)

    def test_available_capacity_increases_after_remove(self):
        loc = _fifo_loc(capacity=3)
        loc.store_containers(['L1', 'L2'])
        loc.remove_containers(['L1'])
        self.assertEqual(loc.AvailableCapacity, 2)

    def test_fifo_removes_first_in_only(self):
        loc = _fifo_loc(capacity=3)
        loc.store_containers(['L1', 'L2', 'L3'])
        # L1 was first in — should be removable
        loc.remove_containers(['L1'])
        self.assertNotIn('L1', loc.ContainerIds)

    def test_fifo_cannot_remove_last_in(self):
        loc = _fifo_loc(capacity=3)
        loc.store_containers(['L1', 'L2', 'L3'])
        with self.assertRaises(ItemNotAccessibleToRemoveException):
            loc.remove_containers(['L3'])

    def test_lifo_removes_last_in_only(self):
        loc = _lifo_loc(capacity=3)
        loc.store_containers(['L1', 'L2', 'L3'])
        loc.remove_containers(['L3'])
        self.assertNotIn('L3', loc.ContainerIds)

    def test_lifo_cannot_remove_first_in(self):
        loc = _lifo_loc(capacity=3)
        loc.store_containers(['L1', 'L2', 'L3'])
        with self.assertRaises(ItemNotAccessibleToRemoveException):
            loc.remove_containers(['L1'])

    def test_clear_containers(self):
        loc = _all_avail_loc()
        loc.store_containers(['L1', 'L2', 'L3'])
        loc.clear_containers()
        self.assertEqual(loc.ContainerIds, [])
        self.assertEqual(loc.AvailableCapacity, loc.Capacity)


# ── Serialization ─────────────────────────────────────────────────────────────

class TestLocationSerialization(unittest.TestCase):

    def test_round_trip_empty_location(self):
        loc = _fifo_loc(capacity=4, loc_id='TEST-1')
        d = Location.to_jsonable_dict(loc)
        restored = Location.from_jsonable_dict(d)
        self.assertEqual(restored.Id, 'TEST-1')
        self.assertEqual(restored.Capacity, 4)
        self.assertEqual(restored.ContainerIds, [])

    def test_round_trip_with_loads(self):
        loc = _all_avail_loc(capacity=5, loc_id='TEST-2')
        loc.store_containers(['L1', 'L2'])
        d = Location.to_jsonable_dict(loc)
        restored = Location.from_jsonable_dict(d)
        self.assertEqual(set(restored.ContainerIds), {'L1', 'L2'})

    def test_round_trip_channel_processor_type_preserved(self):
        loc = _lifo_loc(loc_id='LIFO-1')
        d = Location.to_jsonable_dict(loc)
        restored = Location.from_jsonable_dict(d)
        # LIFO: should still not allow removing first-in
        restored.store_containers(['L1', 'L2'])
        with self.assertRaises(ItemNotAccessibleToRemoveException):
            restored.remove_containers(['L1'])


if __name__ == "__main__":
    unittest.main()
