from typing import Protocol, Iterable, List, Hashable, Dict, Optional
import logging
import unittest
from cooptools.coopEnum import CoopEnum

logger = logging.getLogger(__name__)


def str_format_channel_state(state):
    return '[' + ','.join([str(x) if x is not None else '-' for x in state]) + ']'


def flow(state: Iterable[Optional[Hashable]],
         backwards: bool = False) -> List[Optional[Hashable]]:
    new = [x for x in state if x is not None]

    if backwards:
        new = new + [None for _ in range(len(list(state)) - len(new))]
        logger.info(f"Items flowed backwards: {str_format_channel_state(new)}")
    else:
        new = [None for _ in range(len(list(state)) - len(new))] + new
        logger.info(f"Items flowed forwards: {str_format_channel_state(new)}")

    return new


def removable_positions(
        state: Iterable[Optional[Hashable]],
        include_first: bool = False,
        include_last: bool = False,
        include_all: bool = False
) -> List[int]:
    if include_all:
        return [ii for ii, x in enumerate(state) if x is not None]

    ret = []

    if include_first:
        first_item = next(x for x in reversed(list(state)) if x is not None)
        first_idx = list(state).index(first_item)
        ret.append(first_idx)

    if include_last:
        last_item = next(x for x in list(state) if x is not None)
        last_idx = list(state).index(last_item)
        ret.append(last_idx)

    return ret


def accessible_ids(state: Iterable[Optional[Hashable]],
                   include_first: bool = False,
                   include_last: bool = False,
                   include_all: bool = False) -> Dict[int, Hashable]:
    accessible_ids = removable_positions(
        state=state,
        include_last=include_last,
        include_all=include_all,
        include_first=include_first
    )

    return {ii: list(state)[ii] for ii in accessible_ids}


class ItemNotFoundToRemoveException(Exception):
    def __init__(self, channel_processor,requested, state):
        msg = f"Item <{requested}> requested to remove from {channel_processor.__name__}, but it wasnt found. <{state}>"
        logger.error(msg)
        super().__init__(msg)


class ItemNotAccessibleToRemoveException(Exception):
    def __init__(self, channel_processor, requested, state, available):
        msg = f"Item <{requested}> requested to remove from {channel_processor.__name__}, but item not in removable items <{available}>: <{state}>"
        logger.error(msg)
        super().__init__(msg)


class ItemBlockingToAddException(Exception):
    def __init__(self, channel_processor, requested, pos, state):
        msg = f"Item <{requested}> requested to add to {channel_processor.__name__} at pos {pos}, but item {state[pos]} already in that pos: <{state}>"
        logger.error(msg)
        super().__init__(msg)


class NoRoomToAddException(Exception):
    def __init__(self, channel_processor, requested, state):
        msg = f"Item <{requested}> requested to be added to {channel_processor.__name__}, but there is no room: <{state}>"
        logger.error(msg)
        super().__init__(msg)


class IChannelProcessor(Protocol):
    _allow_push: bool = False

    @classmethod
    def _next_blocker_position(cls,
                               removable: List[int],
                               target_pos: int,
                               state: List[Optional[Hashable]]) -> int:
        """Select which removable slot to sacrifice next when unblocking target_pos.

        Default implementation: single-removable processors always have exactly
        one choice, so just return it.  OMNI-style processors override this to
        pick the shorter side.
        """
        return removable[0]

    @classmethod
    def get_blocking_loads(cls,
                           container_id: Hashable,
                           state: List[Optional[Hashable]]) -> Dict[Hashable, int]:
        """Return the containers that must be removed before *container_id* is
        accessible, in the order they should be removed.

        Keys are container IDs; values are their slot index at the time they
        should be removed (i.e. inside the simulated state at that step).
        Returns ``{}`` if the target is already accessible or absent.
        """
        state = list(state)
        if container_id not in state:
            return {}

        blockers: Dict[Hashable, int] = {}

        for _ in range(len(state)):          # at most capacity iterations
            try:
                removable = cls.get_removable_positions(state)
            except StopIteration:
                break
            if not removable:
                break
            target_pos = state.index(container_id)
            if target_pos in removable:
                break                        # target is now accessible

            chosen = cls._next_blocker_position(removable, target_pos, state)
            blockers[state[chosen]] = chosen
            state[chosen] = None
            state = list(cls.post_process(state))

        return blockers

    @classmethod
    def process(cls,
                state: Iterable[Optional[Hashable]],
                added: Iterable[Hashable] = None,
                removed: Iterable[Hashable] = None,
                allow_replacement: bool = False) -> Iterable[Optional[Hashable]]:
        new_state = [x for x in state]

        # remove removed
        new_state = cls._remove_items(
            removed=removed,
            state=new_state
        )

        # add added
        new_state = cls._add_items(
            added=added,
            state=new_state,
            allow_replacement=allow_replacement
        )

        return new_state

    @classmethod
    def verify_removable(cls,
                         item: Hashable,
                         state: Iterable[Optional[Hashable]]):
        if item not in state:
            raise ItemNotFoundToRemoveException(channel_processor=cls, requested=item, state=state)

        available = cls.get_removeable_ids(state)
        if item not in available.values():
            raise ItemNotAccessibleToRemoveException(
                channel_processor=cls,
                requested=item, 
                state=state, 
                available=available)

    @classmethod
    def _remove_items(cls,
                      state: Iterable[Optional[Hashable]],
                      removed: Iterable[Hashable] = None) -> List[Optional[Hashable]]:
        if removed is None:
            return list(state)

        logger.info(f"Removing Items: {removed}")
        new_state = [x for x in state]

        for item in removed:
            cls.verify_removable(item, new_state)

            idx = list(new_state).index(item)
            new_state[idx] = None
            new_state = cls.post_process(new_state)

        logger.info(f"Items removed: {removed}")
        return new_state

    @classmethod
    def _add_items(cls,
                   state: Iterable[Optional[Hashable]],
                   added: Iterable[Hashable] = None,
                   allow_replacement: bool = False
                   ) -> List[Optional[Hashable]]:
        if added is None:
            return list(state)

        logger.info(f"Adding Items: {added}")
        new_state = [x for x in state]

        for item in added:

            addable_positions = cls.get_addable_positions(new_state)
            idx = None
            if len(addable_positions) > 0:
                idx = addable_positions[0]

            '''Check if there is space in the channel'''
            if ((idx is None) or
                    (not allow_replacement and not cls._allow_push and len([x for x in new_state if x is not None]) + 1 > len(new_state))):
                raise NoRoomToAddException(channel_processor=cls, requested=item, state=new_state)
            '''Check if an item is present at position and it has not been signaled to allow push or replacement'''
            if new_state[idx] is not None and new_state[idx] != item and not allow_replacement and not cls._allow_push:
                raise ItemBlockingToAddException(channel_processor=cls, requested=item, pos=idx, state=new_state)
            '''All Pass, add the item at pos'''
            if cls._allow_push and new_state[idx] is not None:
                new_state.insert(idx, item)
                new_state = new_state[:-1]
            else:
                new_state[idx] = item

            ''' Post Process'''
            new_state = cls.post_process(new_state)

        logger.info(f"Items added: {added}")
        return new_state

    @classmethod
    def get_removeable_ids(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return {ii: state[ii] for ii in cls.get_removable_positions(state)}

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        raise NotImplementedError()

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        raise NotImplementedError()

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Optional[Hashable]]:
        raise NotImplementedError()


class AllAvailableChannelProcessor(IChannelProcessor):
    def __init__(self):
        super().__init__()

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return removable_positions(state=state, include_all=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [ii for ii, x in enumerate(state) if x is None]

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Optional[Hashable]]:
        return list(state)


class AllAvailableFlowChannelProcessor(IChannelProcessor):
    def __init__(self):
        super().__init__()

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return removable_positions(state=state, include_all=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [ii for ii, x in enumerate(state) if x is None]

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Optional[Hashable]]:
        return flow(state)


class AllAvailableFlowBackwardChannelProcessor(IChannelProcessor):
    def __init__(self):
        super().__init__()

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return removable_positions(state=state, include_all=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [ii for ii, x in enumerate(state) if x is None]

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Optional[Hashable]]:
        return flow(state, backwards=True)


class FIFOFlowChannelProcessor(IChannelProcessor):
    def __init__(self):
        super().__init__()

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return removable_positions(state=state, include_first=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [0] if state[0] is None else []

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return flow(state)


class FIFOFlowBackwardChannelProcessor(IChannelProcessor):
    _allow_push = True

    def __init__(self):
        super().__init__()

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return removable_positions(state=state, include_first=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [0] if any(x is None for x in state) else []

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return flow(state, backwards=True)


class LIFOFlowChannelProcessor(IChannelProcessor):
    def __init__(self):
        super().__init__()

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return removable_positions(state=state, include_last=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [0] if state[0] is None else []

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return flow(state)


class LIFOFlowBackwardChannelProcessor(IChannelProcessor):
    _allow_push = True

    def __init__(self):
        super().__init__()

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return removable_positions(state=state, include_last=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [0] if any(x is None for x in state) else []

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return flow(state, backwards=True)


class OMNIChannelProcessor(IChannelProcessor):
    def __init__(self):
        super().__init__()

    @classmethod
    def _next_blocker_position(cls,
                               removable: List[int],
                               target_pos: int,
                               state: List[Optional[Hashable]]) -> int:
        """Peel from whichever end has fewer occupied slots between it and target."""
        left_count  = sum(1 for i, x in enumerate(state) if x is not None and i < target_pos)
        right_count = sum(1 for i, x in enumerate(state) if x is not None and i > target_pos)
        return min(removable) if left_count <= right_count else max(removable)

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        idxs = [ii for ii, x in enumerate(state) if x is not None]
        if len(idxs) == 0:
            return []
        
        return list(set([min(idxs), max(idxs)]))

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        idxs = [ii for ii, x in enumerate(state) if x is None]
        if len(idxs) == 0:
            return []
        
        return list(set([min(idxs), max(idxs)]))

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return list(state)


class OMNIFlowChannelProcessor(IChannelProcessor):
    def __init__(self):
        super().__init__()

    @classmethod
    def _next_blocker_position(cls,
                               removable: List[int],
                               target_pos: int,
                               state: List[Optional[Hashable]]) -> int:
        left_count  = sum(1 for i, x in enumerate(state) if x is not None and i < target_pos)
        right_count = sum(1 for i, x in enumerate(state) if x is not None and i > target_pos)
        return min(removable) if left_count <= right_count else max(removable)

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        idxs = [ii for ii, x in enumerate(state) if x is not None]
        if len(idxs) == 0:
            return []
        
        return list(set([min(idxs), max(idxs)]))

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        idxs = [ii for ii, x in enumerate(state) if x is None]
        if len(idxs) == 0:
            return []
        
        return list(set([min(idxs), max(idxs)]))

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return flow(state)


class OMNIFlowBackwardChannelProcessor(IChannelProcessor):
    _allow_push = True

    def __init__(self):
        super().__init__()

    @classmethod
    def _next_blocker_position(cls,
                               removable: List[int],
                               target_pos: int,
                               state: List[Optional[Hashable]]) -> int:
        left_count  = sum(1 for i, x in enumerate(state) if x is not None and i < target_pos)
        right_count = sum(1 for i, x in enumerate(state) if x is not None and i > target_pos)
        return min(removable) if left_count <= right_count else max(removable)

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        idxs = [ii for ii, x in enumerate(state) if x is not None]
        if len(idxs) == 0:
            return []
        
        return list(set([min(idxs), max(idxs)]))

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        idxs = [ii for ii, x in enumerate(state) if x is None]
        if len(idxs) == 0:
            return []
        
        return list(set([min(idxs), max(idxs)]))

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return flow(state, backwards=True)



class MyTestCases(unittest.TestCase):
    def test_allavail_1(self):
        state = [None for ii in range(5)]
        cp = AllAvailableChannelProcessor()
        state = cp.process(state, added=['a', 'b'])
        state = cp.process(state, added=['c', 'd'])
        self.assertTrue(all(x in state for x in ['a', 'b', 'c', 'd']))
        self.assertEqual(len([x for x in state if x is not None]), 4)

        state = cp.process(state, removed=['c', 'a'])
        self.assertTrue(all(x in state for x in ['b', 'd']))
        self.assertEqual(len([x for x in state if x is not None]), 2)


    def test_fifo_1(self):
        state = [None for ii in range(5)]

        cp = FIFOFlowChannelProcessor()
        state = cp.process(state=state,
                               added=['a', 'b', 'c', 'd', 'e'])

        self.assertTrue(all(x in state for x in ['a', 'b', 'c', 'd', 'e']))
        self.assertEqual(len([x for x in state if x is not None]), 5)

        self.assertRaises(NoRoomToAddException, lambda: cp.process(state=state,
                               added=['f']))

        self.assertRaises(ItemNotAccessibleToRemoveException, lambda: cp.process(state=state,
                               removed=['e']))

    def test_lifo_1(self):
        state = [None for ii in range(5)]

        cp = LIFOFlowChannelProcessor()
        new_state = cp.process(state=state,
                               added=['a', 'b', 'c', 'd', 'e'])

        new_state = cp.process(state=new_state,
                               removed=['e'])
        self.assertRaises(ItemNotAccessibleToRemoveException, lambda: cp.process(state=new_state,
                               removed=['a']))

    # ── get_blocking_loads tests ──────────────────────────────────────────────

    def test_blocking_allavailable(self):
        # AllAvailable: every item is always removable → never any blockers
        cp = AllAvailableChannelProcessor()
        state = [None, 'a', 'b', 'c', None]
        self.assertEqual(cp.get_blocking_loads('b', state), {})
        self.assertEqual(cp.get_blocking_loads('a', state), {})

    def test_blocking_allavailable_flow(self):
        # Flow variants also expose all slots
        for CpType in (AllAvailableFlowChannelProcessor,
                       AllAvailableFlowBackwardChannelProcessor):
            cp = CpType()
            state = cp.process([None]*5, added=['a', 'b', 'c'])
            self.assertEqual(cp.get_blocking_loads('b', state), {})

    def test_blocking_fifo_flow(self):
        # FIFO forward: items pack right, removable = rightmost (oldest).
        # State after adding a,b,c → [None, None, 'c', 'b', 'a']
        cp = FIFOFlowChannelProcessor()
        state = cp.process([None]*5, added=['a', 'b', 'c'])
        # 'a' is oldest (rightmost), directly removable → no blockers
        self.assertEqual(cp.get_blocking_loads('a', state), {})
        # 'b' is blocked by 'a'
        blockers_b = cp.get_blocking_loads('b', state)
        self.assertIn('a', blockers_b)
        self.assertNotIn('b', blockers_b)
        self.assertNotIn('c', blockers_b)
        # 'c' (newest, leftmost) is blocked by 'a' then 'b'
        blockers_c = cp.get_blocking_loads('c', state)
        self.assertIn('a', blockers_c)
        self.assertIn('b', blockers_c)
        self.assertNotIn('c', blockers_c)
        # Order: 'a' must come before 'b' in the removal sequence
        keys = list(blockers_c.keys())
        self.assertLess(keys.index('a'), keys.index('b'))

    def test_blocking_fifo_backward(self):
        # FIFOBackward: items pack left, removable = rightmost (oldest on right).
        # After adding a,b,c → ['c', 'b', 'a', None, None]
        cp = FIFOFlowBackwardChannelProcessor()
        state = cp.process([None]*5, added=['a', 'b', 'c'])
        self.assertEqual(cp.get_blocking_loads('a', state), {})  # 'a' is rightmost → removable
        blockers_b = cp.get_blocking_loads('b', state)
        self.assertIn('a', blockers_b)
        self.assertNotIn('b', blockers_b)

    def test_blocking_lifo_flow(self):
        # LIFO forward: items pack right, removable = leftmost (newest on left).
        # After adding a,b,c → [None, None, 'c', 'b', 'a']
        cp = LIFOFlowChannelProcessor()
        state = cp.process([None]*5, added=['a', 'b', 'c'])
        # 'c' is newest (leftmost), directly removable → no blockers
        self.assertEqual(cp.get_blocking_loads('c', state), {})
        # 'b' blocked by 'c'
        blockers_b = cp.get_blocking_loads('b', state)
        self.assertIn('c', blockers_b)
        self.assertNotIn('b', blockers_b)
        # 'a' (oldest, rightmost) blocked by 'c' then 'b'
        blockers_a = cp.get_blocking_loads('a', state)
        self.assertIn('c', blockers_a)
        self.assertIn('b', blockers_a)
        keys = list(blockers_a.keys())
        self.assertLess(keys.index('c'), keys.index('b'))

    def test_blocking_lifo_backward(self):
        # LIFOBackward: items pack left, removable = leftmost (newest).
        # After adding a,b,c → ['c', 'b', 'a', None, None]
        cp = LIFOFlowBackwardChannelProcessor()
        state = cp.process([None]*5, added=['a', 'b', 'c'])
        self.assertEqual(cp.get_blocking_loads('c', state), {})   # 'c' leftmost → removable
        blockers_a = cp.get_blocking_loads('a', state)
        self.assertIn('c', blockers_a)
        self.assertIn('b', blockers_a)
        keys = list(blockers_a.keys())
        self.assertLess(keys.index('c'), keys.index('b'))

    def test_blocking_omni(self):
        # OMNI (no flow): both ends accessible, choose shorter side.
        cp = OMNIChannelProcessor()
        # State: [None, 'a', 'b', 'c', 'd']
        # target='b' (idx 2): left has 'a' (1 item), right has 'c','d' (2 items) → remove 'a'
        state = [None, 'a', 'b', 'c', 'd']
        blockers = cp.get_blocking_loads('b', state)
        self.assertIn('a', blockers)
        self.assertNotIn('c', blockers)
        self.assertNotIn('d', blockers)
        # target='c' (idx 3): left has 'a','b' (2), right has 'd' (1) → remove 'd'
        blockers = cp.get_blocking_loads('c', state)
        self.assertIn('d', blockers)
        self.assertNotIn('a', blockers)
        self.assertNotIn('b', blockers)
        # target at an end is immediately accessible
        self.assertEqual(cp.get_blocking_loads('a', state), {})
        self.assertEqual(cp.get_blocking_loads('d', state), {})

    def test_blocking_omni_flow(self):
        # OMNIFlow: both ends accessible, items reflow after each removal.
        cp = OMNIFlowChannelProcessor()
        state = cp.process([None]*5, added=['a', 'b', 'c', 'd', 'e'])
        # All slots full: [None, 'a', 'b', 'c', 'd', 'e'] → packed → ['a','b','c','d','e'] (len=5)
        # 'a','e' at ends → immediately accessible
        self.assertEqual(cp.get_blocking_loads('a', state), {})
        self.assertEqual(cp.get_blocking_loads('e', state), {})
        # 'c' in middle: need to peel from shorter side (both equal → choose left)
        blockers = cp.get_blocking_loads('c', state)
        self.assertEqual(len(blockers), 2)   # 2 items on each side, shortest = 2

    def test_blocking_omni_flow_backward(self):
        # OMNIFlowBackward: same logic, backward flow.
        cp = OMNIFlowBackwardChannelProcessor()
        state = cp.process([None]*5, added=['a', 'b', 'c', 'd', 'e'])
        self.assertEqual(cp.get_blocking_loads('a', state), {})
        self.assertEqual(cp.get_blocking_loads('e', state), {})
        blockers = cp.get_blocking_loads('c', state)
        self.assertEqual(len(blockers), 2)

    def test_blocking_absent_container(self):
        # Container not in state → empty dict
        cp = FIFOFlowChannelProcessor()
        state = [None, None, 'a', 'b', 'c']
        self.assertEqual(cp.get_blocking_loads('z', state), {})


class ChannelProcessorType(CoopEnum):
    AllAvailableFlowBackwardChannelProcessor = AllAvailableFlowBackwardChannelProcessor()
    AllAvailableFlowChannelProcessor = AllAvailableFlowChannelProcessor()
    AllAvailableChannelProcessor = AllAvailableChannelProcessor()
    FIFOFlowBackwardChannelProcessor = FIFOFlowBackwardChannelProcessor()
    FIFOFlowChannelProcessor = FIFOFlowChannelProcessor()
    LIFOFlowBackwardChannelProcessor = LIFOFlowBackwardChannelProcessor()
    LIFOFlowChannelProcessor = LIFOFlowChannelProcessor()
    OMNIChannelProcessor = OMNIFlowChannelProcessor()
    OMNIFlowChannelProcessor = OMNIFlowChannelProcessor()
    OMNIFlowBackwardChannelProcessor = OMNIFlowBackwardChannelProcessor()

if __name__ == "__main__":
    unittest.main()
