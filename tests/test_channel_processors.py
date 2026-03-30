"""
Tests for channel_processors.py

Covers all 10 processor types:
- AllAvailableChannelProcessor
- AllAvailableFlowChannelProcessor / AllAvailableFlowBackwardChannelProcessor
- FIFOFlowChannelProcessor / FIFOFlowBackwardChannelProcessor
- LIFOFlowChannelProcessor / LIFOFlowBackwardChannelProcessor
- OMNIChannelProcessor / OMNIFlowChannelProcessor / OMNIFlowBackwardChannelProcessor
"""
import unittest

from coopstorage.storage.loc_load.channel_processors import (
    AllAvailableChannelProcessor,
    AllAvailableFlowChannelProcessor,
    AllAvailableFlowBackwardChannelProcessor,
    FIFOFlowChannelProcessor,
    FIFOFlowBackwardChannelProcessor,
    LIFOFlowChannelProcessor,
    LIFOFlowBackwardChannelProcessor,
    OMNIChannelProcessor,
    OMNIFlowChannelProcessor,
    OMNIFlowBackwardChannelProcessor,
    NoRoomToAddException,
    ItemNotAccessibleToRemoveException,
    ItemNotFoundToRemoveException,
    ChannelProcessorType,
)


def _empty(n=5):
    return [None] * n


# ── AllAvailableChannelProcessor ──────────────────────────────────────────────

class TestAllAvailableChannelProcessor(unittest.TestCase):
    cp = AllAvailableChannelProcessor()

    def test_add_and_remove_any_position(self):
        state = self.cp.process(_empty(), added=['a', 'b', 'c'])
        self.assertIn('a', state)
        state = self.cp.process(state, removed=['b'])
        self.assertNotIn('b', state)
        self.assertIn('a', state)
        self.assertIn('c', state)

    def test_add_fills_empty_slots(self):
        state = self.cp.process(_empty(3), added=['x', 'y', 'z'])
        self.assertEqual(sorted(x for x in state if x), ['x', 'y', 'z'])

    def test_no_room_raises(self):
        state = self.cp.process(_empty(2), added=['a', 'b'])
        with self.assertRaises(NoRoomToAddException):
            self.cp.process(state, added=['c'])

    def test_remove_unknown_item_raises(self):
        state = self.cp.process(_empty(), added=['a'])
        with self.assertRaises(ItemNotFoundToRemoveException):
            self.cp.process(state, removed=['z'])


# ── FIFO ──────────────────────────────────────────────────────────────────────

class TestFIFOFlowChannelProcessor(unittest.TestCase):
    cp = FIFOFlowChannelProcessor()

    def test_add_and_remove_first_in_first_out(self):
        state = _empty(5)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        removable = self.cp.get_removeable_ids(state)
        # First added should be the one removable
        self.assertIn('a', removable.values())

    def test_cannot_remove_last_item(self):
        state = _empty(5)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        with self.assertRaises(ItemNotAccessibleToRemoveException):
            self.cp.process(state, removed=['c'])

    def test_no_room_raises(self):
        state = _empty(3)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        with self.assertRaises(NoRoomToAddException):
            self.cp.process(state, added=['d'])

    def test_items_flow_forward_after_remove(self):
        state = _empty(5)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        state = self.cp.process(state, removed=['a'])
        # After remove + flow, 'b' should now be the removable one
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('b', removable.values())


# ── LIFO ──────────────────────────────────────────────────────────────────────

class TestLIFOFlowChannelProcessor(unittest.TestCase):
    cp = LIFOFlowChannelProcessor()

    def test_last_in_is_removable(self):
        state = _empty(5)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('c', removable.values())

    def test_cannot_remove_first_item(self):
        state = _empty(5)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        with self.assertRaises(ItemNotAccessibleToRemoveException):
            self.cp.process(state, removed=['a'])

    def test_lifo_order(self):
        state = _empty(5)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        state = self.cp.process(state, removed=['c'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('b', removable.values())
        self.assertNotIn('a', removable.values())


# ── FIFO Backward (push) ──────────────────────────────────────────────────────

class TestFIFOFlowBackwardChannelProcessor(unittest.TestCase):
    cp = FIFOFlowBackwardChannelProcessor()

    def test_push_beyond_capacity_drops_oldest(self):
        """Backward FIFO with _allow_push pushes and drops the tail."""
        state = _empty(3)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        # All slots filled; push 'd' — 'a' (first in) should be pushed off
        state = self.cp.process(state, added=['d'])
        self.assertIn('d', state)
        self.assertNotIn('a', state)

    def test_first_in_is_removable(self):
        state = _empty(5)
        state = self.cp.process(state, added=['a', 'b'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('a', removable.values())


# ── LIFO Backward (push) ──────────────────────────────────────────────────────

class TestLIFOFlowBackwardChannelProcessor(unittest.TestCase):
    cp = LIFOFlowBackwardChannelProcessor()

    def test_last_in_is_removable(self):
        state = _empty(5)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('c', removable.values())


# ── OMNI ──────────────────────────────────────────────────────────────────────

class TestOMNIChannelProcessor(unittest.TestCase):
    cp = OMNIChannelProcessor()

    def test_can_remove_first_and_last(self):
        state = _empty(5)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        removable = list(self.cp.get_removeable_ids(state).values())
        self.assertIn('a', removable)
        self.assertIn('c', removable)

    def test_cannot_remove_middle(self):
        state = _empty(5)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        with self.assertRaises(ItemNotAccessibleToRemoveException):
            self.cp.process(state, removed=['b'])


# ── AllAvailable Flow variants ────────────────────────────────────────────────

class TestAllAvailableFlowChannelProcessor(unittest.TestCase):
    def test_items_flow_forward_after_remove(self):
        cp = AllAvailableFlowChannelProcessor()
        state = _empty(5)
        state = cp.process(state, added=['a', 'b', 'c'])
        state = cp.process(state, removed=['b'])
        none_count = state.count(None)
        # After forward flow, Nones should be at the start
        for i in range(none_count):
            self.assertIsNone(state[i])

    def test_items_flow_backward_after_remove(self):
        cp = AllAvailableFlowBackwardChannelProcessor()
        state = _empty(5)
        state = cp.process(state, added=['a', 'b', 'c'])
        state = cp.process(state, removed=['b'])
        none_count = state.count(None)
        # After backward flow, Nones should be at the end
        for i in range(none_count):
            self.assertIsNone(state[-(i + 1)])


# ── OMNI Flow variants ────────────────────────────────────────────────────────

class TestOMNIFlowChannelProcessor(unittest.TestCase):
    def test_omni_flow_removable_both_ends(self):
        cp = OMNIFlowChannelProcessor()
        state = _empty(5)
        state = cp.process(state, added=['a', 'b', 'c'])
        removable = list(cp.get_removeable_ids(state).values())
        self.assertIn('a', removable)
        self.assertIn('c', removable)

    def test_omni_flow_backward_removable_both_ends(self):
        cp = OMNIFlowBackwardChannelProcessor()
        state = _empty(5)
        state = cp.process(state, added=['a', 'b', 'c'])
        removable = list(cp.get_removeable_ids(state).values())
        self.assertIn('a', removable)
        self.assertIn('c', removable)


# ── ChannelProcessorType enum ─────────────────────────────────────────────────

class TestChannelProcessorType(unittest.TestCase):
    def test_all_enum_values_are_instances(self):
        """Every member of ChannelProcessorType should be a processor instance."""
        for member in ChannelProcessorType:
            self.assertIsNotNone(member.value)
            self.assertTrue(hasattr(member.value, 'process'),
                            f"{member.name} value is not a valid processor")

    def test_lookup_by_name(self):
        cp = ChannelProcessorType.by_str('FIFOFlowChannelProcessor')
        self.assertIsNotNone(cp)


if __name__ == "__main__":
    unittest.main()
