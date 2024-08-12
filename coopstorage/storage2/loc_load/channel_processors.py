from typing import Protocol, Iterable, List, Hashable, Dict, Optional
import logging
import unittest

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
    def __init__(self, requested, state):
        msg = f"Item <{requested}> requested to remove, but it wasnt found. <{state}>"
        logger.error(msg)
        super().__init__(msg)


class ItemNotAccessibleToRemoveException(Exception):
    def __init__(self, requested, state, available):
        msg = f"Item <{requested}> requested to remove, but item not in available items <{available}>: <{state}>"
        logger.error(msg)
        super().__init__(msg)


class ItemBlockingToAddException(Exception):
    def __init__(self, requested, pos, state):
        msg = f"Item <{requested}> requested to add to pos {pos}, but item {state[pos]} already in that pos: <{state}>"
        logger.error(msg)
        super().__init__(msg)


class NoRoomToAddException(Exception):
    def __init__(self, requested, state):
        msg = f"Item <{requested}> requested to be added, but there is no room: <{state}>"
        logger.error(msg)
        super().__init__(msg)


class IChannelProcessor(Protocol):
    _allow_push: bool = False

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
            raise ItemNotFoundToRemoveException(requested=item, state=state)

        available = cls.get_removeable_ids(state)
        if item not in available.values():
            raise ItemNotAccessibleToRemoveException(requested=item, state=state, available=available)

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
                    (not allow_replacement and len([x for x in new_state if x is not None]) + 1 > len(new_state))):
                raise NoRoomToAddException(requested=item, state=new_state)
            '''Check if an item is present at position and it has not been signaled to allow push or replacement'''
            if new_state[idx] is not None and new_state[idx] != item and not allow_replacement and not cls._allow_push:
                raise ItemBlockingToAddException(requested=item, pos=idx, state=new_state)
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
        return [0]

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
        return [0]

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return flow(state, backwards=True)


class OMNIChannelProcessor(IChannelProcessor):
    def __init__(self):
        super().__init__()

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return removable_positions(state=state, include_first=True, include_last=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [0] if state[0] is None else []

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return list(state)


class OMNIFlowChannelProcessor(IChannelProcessor):
    def __init__(self):
        super().__init__()

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return removable_positions(state=state, include_first=True, include_last=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [0] if state[0] is None else []

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return flow(state)


class OMNIFlowBackwardChannelProcessor(IChannelProcessor):
    _allow_push = True

    def __init__(self):
        super().__init__()

    @classmethod
    def get_removable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return removable_positions(state=state, include_first=True, include_last=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [0] if state[0] is None else []

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


if __name__ == "__main__":
    unittest.main()
