"""
Tests for channel_processors.py

Covers all 14 processor types:
- AllAvailableChannelProcessor
- AllAvailableFlowChannelProcessor / AllAvailableFlowBackwardChannelProcessor
- FIFOFlowChannelProcessor / FIFOFlowBackwardChannelProcessor
- LIFOFlowChannelProcessor / LIFOFlowBackwardChannelProcessor
- FIFONoFlowChannelProcessor / FIFONoFlowPushChannelProcessor
- LIFONoFlowChannelProcessor / LIFONoFlowPushChannelProcessor
- OMNIChannelProcessor / OMNIFlowChannelProcessor / OMNIFlowBackwardChannelProcessor
"""
import unittest

from coopstorage.storage.loc_load.channel_processors import (
    AllAvailableChannelProcessor,
    AllAvailableFlowChannelProcessor,
    AllAvailableFlowBackwardChannelProcessor,
    FIFOFlowChannelProcessor,
    FIFOFlowBackwardChannelProcessor,
    FIFONoFlowChannelProcessor,
    FIFONoFlowPushChannelProcessor,
    LIFOFlowChannelProcessor,
    LIFOFlowBackwardChannelProcessor,
    LIFONoFlowChannelProcessor,
    LIFONoFlowPushChannelProcessor,
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

    def test_push_beyond_capacity_raises(self):
        """Backward FIFO raises NoRoomToAddException when channel is full (no empty slots)."""
        from coopstorage.storage.loc_load.channel_processors import NoRoomToAddException
        state = _empty(3)
        state = self.cp.process(state, added=['a', 'b', 'c'])
        # All slots filled; process() should raise rather than push-and-drop
        with self.assertRaises(NoRoomToAddException):
            self.cp.process(state, added=['d'])

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


# ── FIFONoFlow ────────────────────────────────────────────────────────────────

class TestFIFONoFlowChannelProcessor(unittest.TestCase):
    cp = FIFONoFlowChannelProcessor()

    def test_items_fill_deep_to_shallow(self):
        # Items occupy slots from deepest (N-1) toward shallowest (0).
        # With 5 slots, adding a, b, c fills slots 4, 3, 2.
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        occupied = [x for x in state if x is not None]
        self.assertEqual(len(occupied), 3)
        self.assertEqual(state[4], 'a')
        self.assertEqual(state[3], 'b')
        self.assertEqual(state[2], 'c')

    def test_first_in_is_removable(self):
        # Oldest item sits at the deepest slot → always removable first (FIFO).
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('a', removable.values())

    def test_newest_not_removable(self):
        # Most recently added item is at the shallowest occupied slot → not removable.
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        with self.assertRaises(ItemNotAccessibleToRemoveException):
            self.cp.process(state, removed=['c'])

    def test_fifo_order_across_removes(self):
        # Removing 'a' exposes 'b' as the next oldest (deepest remaining).
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        state = self.cp.process(state, removed=['a'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('b', removable.values())
        self.assertNotIn('a', removable.values())
        self.assertNotIn('c', removable.values())

    def test_add_after_remove_fills_adjacent_to_pack(self):
        # After removing 'a' (slot 4), the freed slot is NOT reused;
        # the next add goes to slot 1 (deepest None in prefix before 'c' at slot 2).
        #   state after remove: [-, -, c, b, -]
        #   prefix scan: 0=None, 1=None, 2=c → stop → addable = [1]
        #   add 'd' → [-, d, c, b, -]
        #   deepest occupied = b at slot 3  ✓ FIFO: b is older than c and d
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        state = self.cp.process(state, removed=['a'])
        addable = self.cp.get_addable_positions(state)
        self.assertEqual(addable, [1])
        state = self.cp.process(state, added=['d'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('b', removable.values())

    def test_no_room_raises(self):
        state = self.cp.process(_empty(3), added=['a', 'b', 'c'])
        with self.assertRaises(NoRoomToAddException):
            self.cp.process(state, added=['d'])

    def test_addable_blocked_when_pack_reaches_slot_0(self):
        # When an item occupies slot 0, there is no contiguous None prefix → not addable.
        state = self.cp.process(_empty(3), added=['a', 'b'])
        # state = [-, b, a];  prefix scan: slot 0 = None, slot 1 = b → stop → addable = [0]
        addable = self.cp.get_addable_positions(state)
        self.assertEqual(addable, [0])
        state = self.cp.process(state, added=['c'])
        # now full: [c, b, a]; slot 0 = c (not None) → addable = []
        self.assertEqual(self.cp.get_addable_positions(state), [])


# ── LIFONoFlow ────────────────────────────────────────────────────────────────

class TestLIFONoFlowChannelProcessor(unittest.TestCase):
    cp = LIFONoFlowChannelProcessor()

    def test_items_fill_deep_to_shallow(self):
        # Same fill direction as FIFONoFlow: deep (N-1) → shallow (0).
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        self.assertEqual(state[4], 'a')
        self.assertEqual(state[3], 'b')
        self.assertEqual(state[2], 'c')

    def test_last_in_is_removable(self):
        # Newest item sits at the shallowest occupied slot → removable first (LIFO).
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('c', removable.values())

    def test_oldest_not_removable(self):
        # First-added item is at the deepest slot → not immediately removable.
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        with self.assertRaises(ItemNotAccessibleToRemoveException):
            self.cp.process(state, removed=['a'])

    def test_lifo_order_across_removes(self):
        # Removing 'c' exposes 'b' as the next newest (shallowest remaining).
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        state = self.cp.process(state, removed=['c'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('b', removable.values())
        self.assertNotIn('c', removable.values())
        self.assertNotIn('a', removable.values())

    def test_add_after_remove_fills_vacated_slot(self):
        # After removing 'c' (slot 2), next add refills slot 2 and it immediately
        # becomes the shallowest occupied → removable next (LIFO).
        #   state after remove: [-, -, -, b, a]
        #   prefix scan: 0,1,2=None, 3=b → stop → addable = [2]
        #   add 'd' → [-, -, d, b, a]
        #   shallowest occupied = d at slot 2  ✓ LIFO: d was just added
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        state = self.cp.process(state, removed=['c'])
        addable = self.cp.get_addable_positions(state)
        self.assertEqual(addable, [2])
        state = self.cp.process(state, added=['d'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('d', removable.values())

    def test_no_room_raises(self):
        state = self.cp.process(_empty(3), added=['a', 'b', 'c'])
        with self.assertRaises(NoRoomToAddException):
            self.cp.process(state, added=['d'])


# ── FIFONoFlowPush ────────────────────────────────────────────────────────────

class TestFIFONoFlowPushChannelProcessor(unittest.TestCase):
    cp = FIFONoFlowPushChannelProcessor()

    def test_push_shifts_items_right(self):
        # Each add pushes at slot 0, shifting existing items right (no flow).
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        self.assertEqual(state[0], 'c')
        self.assertEqual(state[1], 'b')
        self.assertEqual(state[2], 'a')

    def test_first_in_is_removable(self):
        # Oldest item ends up at the rightmost slot → removable first (FIFO).
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('a', removable.values())

    def test_newest_not_removable(self):
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        with self.assertRaises(ItemNotAccessibleToRemoveException):
            self.cp.process(state, removed=['c'])

    def test_fifo_order_after_remove_and_push(self):
        # Remove 'a', then push 'd'. 'b' should be next removable (older than 'c' and 'd').
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        state = self.cp.process(state, removed=['a'])
        state = self.cp.process(state, added=['d'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('b', removable.values())

    def test_no_room_raises_when_full(self):
        state = self.cp.process(_empty(3), added=['a', 'b', 'c'])
        with self.assertRaises(NoRoomToAddException):
            self.cp.process(state, added=['d'])


# ── LIFONoFlowPush ────────────────────────────────────────────────────────────

class TestLIFONoFlowPushChannelProcessor(unittest.TestCase):
    cp = LIFONoFlowPushChannelProcessor()

    def test_push_shifts_items_right(self):
        # Each add pushes at slot 0, shifting existing items right (no flow).
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        self.assertEqual(state[0], 'c')
        self.assertEqual(state[1], 'b')
        self.assertEqual(state[2], 'a')

    def test_last_in_is_removable(self):
        # Newest item is at slot 0 (leftmost) → removable first (LIFO).
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('c', removable.values())

    def test_oldest_not_removable(self):
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        with self.assertRaises(ItemNotAccessibleToRemoveException):
            self.cp.process(state, removed=['a'])

    def test_lifo_order_after_remove_and_push(self):
        # Remove 'c', then push 'd'. 'd' should be immediately removable (newest).
        state = self.cp.process(_empty(5), added=['a', 'b', 'c'])
        state = self.cp.process(state, removed=['c'])
        state = self.cp.process(state, added=['d'])
        removable = self.cp.get_removeable_ids(state)
        self.assertIn('d', removable.values())

    def test_no_room_raises_when_full(self):
        state = self.cp.process(_empty(3), added=['a', 'b', 'c'])
        with self.assertRaises(NoRoomToAddException):
            self.cp.process(state, added=['d'])


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
