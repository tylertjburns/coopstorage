"""
Tests for transferRequest.py

Covers:
- TransferRequestCriteria construction
- TransferRequest.verify — all 3 valid transfer types
- TransferRequest.Ready — container accessible, dest has room
- to_jsonable_dict / from_jsonable_dict round-trip (with and without optional locs)
"""
import unittest

import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.channel_processors as cps
from coopstorage.storage.loc_load.location import Location
from coopstorage.storage.loc_load.transferRequest import (
    TransferRequestCriteria,
    TransferRequest,
)
from coopstorage.storage.loc_load.qualifiers import LocationQualifier, ContainerQualifier

# ── helpers ───────────────────────────────────────────────────────────────────

def _loc(loc_id='A', capacity=3):
    return Location(
        id=loc_id,
        location_meta=dcs.LocationMeta(
            dims=(10, 10, 10),
            channel_processor=cps.AllAvailableChannelProcessor(),
            capacity=capacity,
        ),
        coords=(0, 0, 0),
    )

def _fifo_loc(loc_id='B', capacity=3):
    return Location(
        id=loc_id,
        location_meta=dcs.LocationMeta(
            dims=(10, 10, 10),
            channel_processor=cps.FIFOFlowChannelProcessor(),
            capacity=capacity,
        ),
        coords=(0, 0, 0),
    )

def _load(load_id='L1'):
    return dcs.Container(id=load_id)


# ── TransferRequestCriteria ───────────────────────────────────────────────────

class TestTransferRequestCriteria(unittest.TestCase):

    def test_new_container_only(self):
        """Criteria with only new_container is valid."""
        c = TransferRequestCriteria(new_container=_load())
        self.assertIsNotNone(c.new_container)
        self.assertIsNone(c.source_loc_query_args)
        self.assertIsNone(c.dest_loc_query_args)

    def test_query_args_only(self):
        c = TransferRequestCriteria(
            container_query_args=ContainerQualifier(),
            dest_loc_query_args=LocationQualifier(at_least_capacity=1),
        )
        self.assertIsNotNone(c.container_query_args)


# ── TransferRequest.verify ────────────────────────────────────────────────────

class TestTransferRequestVerify(unittest.TestCase):

    def test_type1_store_new_container_at_dest(self):
        """source=None, container firm, dest firm → store new container."""
        tr = TransferRequest(
            criteria=TransferRequestCriteria(new_container=_load()),
            container=_load(),
            source_loc=None,
            dest_loc=_loc(),
        )
        self.assertTrue(tr.verify())

    def test_type2_transfer_from_source_to_dest(self):
        """source firm, container firm, dest firm → transfer."""
        tr = TransferRequest(
            criteria=TransferRequestCriteria(new_container=_load()),
            container=_load(),
            source_loc=_loc('SRC'),
            dest_loc=_loc('DST'),
        )
        self.assertTrue(tr.verify())

    def test_type3_remove_from_source(self):
        """source firm, container firm, dest=None → remove."""
        tr = TransferRequest(
            criteria=TransferRequestCriteria(new_container=_load()),
            container=_load(),
            source_loc=_loc('SRC'),
            dest_loc=None,
        )
        self.assertTrue(tr.verify())

    def test_invalid_no_load_raises(self):
        """load=None, source=None, dest=None → should raise on verify."""
        with self.assertRaises(ValueError):
            TransferRequest(
                criteria=TransferRequestCriteria(new_container=_load()),
                container=None,
                source_loc=None,
                dest_loc=None,
            )


# ── TransferRequest.Ready ─────────────────────────────────────────────────────

class TestTransferRequestReady(unittest.TestCase):

    def test_ready_new_container_to_empty_dest(self):
        dest = _loc(capacity=2)
        tr = TransferRequest(
            criteria=TransferRequestCriteria(new_container=_load()),
            container=_load(),
            source_loc=None,
            dest_loc=dest,
        )
        self.assertTrue(tr.Ready)

    def test_not_ready_dest_full(self):
        dest = _loc(capacity=1)
        dest.store_containers(['EXISTING'])
        tr = TransferRequest(
            criteria=TransferRequestCriteria(new_container=_load()),
            container=_load(),
            source_loc=None,
            dest_loc=dest,
        )
        self.assertFalse(tr.Ready)

    def test_ready_transfer_accessible_container(self):
        src = _loc('SRC', capacity=3)
        src.store_containers(['L1'])
        dest = _loc('DST', capacity=3)
        tr = TransferRequest(
            criteria=TransferRequestCriteria(new_container=_load()),
            container=_load('L1'),
            source_loc=src,
            dest_loc=dest,
        )
        self.assertTrue(tr.Ready)

    def test_not_ready_container_not_accessible_in_source(self):
        """L1 is buried in a FIFO loc behind L2 — not accessible."""
        src = _fifo_loc('SRC', capacity=3)
        src.store_containers(['L1', 'L2'])  # L1 first in, but L2 came after
        # With FIFO, only L1 is extractable (first-in = front of queue)
        # So trying to move L2 should not be ready
        dest = _loc('DST', capacity=3)
        tr = TransferRequest(
            criteria=TransferRequestCriteria(new_container=_load()),
            container=_load('L2'),
            source_loc=src,
            dest_loc=dest,
        )
        self.assertFalse(tr.Ready)

    def test_ready_remove_only(self):
        """Remove from source, no dest — always ready if container accessible."""
        src = _loc('SRC', capacity=3)
        src.store_containers(['L1'])
        tr = TransferRequest(
            criteria=TransferRequestCriteria(new_container=_load()),
            container=_load('L1'),
            source_loc=src,
            dest_loc=None,
        )
        self.assertTrue(tr.Ready)


# ── Serialization ─────────────────────────────────────────────────────────────

class TestTransferRequestSerialization(unittest.TestCase):

    def _make_tr(self, source=None, dest=None):
        return TransferRequest(
            criteria=TransferRequestCriteria(new_container=_load()),
            container=_load('L99'),
            source_loc=source,
            dest_loc=dest,
        )

    def test_round_trip_with_both_locs(self):
        src = _loc('S', capacity=2)
        dst = _loc('D', capacity=2)
        tr = self._make_tr(source=src, dest=dst)
        d = TransferRequest.to_jsonable_dict(tr)
        restored = TransferRequest.from_jsonable_dict(d)
        self.assertEqual(restored.container.id, 'L99')
        self.assertEqual(restored.source_loc.Id, 'S')
        self.assertEqual(restored.dest_loc.Id, 'D')

    def test_round_trip_no_source(self):
        dst = _loc('D', capacity=2)
        tr = self._make_tr(source=None, dest=dst)
        d = TransferRequest.to_jsonable_dict(tr)
        restored = TransferRequest.from_jsonable_dict(d)
        self.assertIsNone(restored.source_loc)
        self.assertEqual(restored.dest_loc.Id, 'D')

    def test_round_trip_no_dest(self):
        src = _loc('S', capacity=2)
        tr = self._make_tr(source=src, dest=None)
        d = TransferRequest.to_jsonable_dict(tr)
        restored = TransferRequest.from_jsonable_dict(d)
        self.assertEqual(restored.source_loc.Id, 'S')
        self.assertIsNone(restored.dest_loc)


if __name__ == "__main__":
    unittest.main()
