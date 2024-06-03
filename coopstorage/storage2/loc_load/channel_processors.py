from typing import Protocol, Iterable, List, Hashable, Dict, Optional
import logging

logger = logging.getLogger(__name__)

def flow(state: Iterable[Optional[Hashable]],
         backwards: bool = False) -> List[Optional[Hashable]]:
    new = [x for x in state if x is not None]

    if backwards:
        new = new + [None for _ in range(len(list(state)) - len(new))]
    else:
        new = [None for _ in range(len(list(state)) - len(new))] + new

    return new

def accessible(state: Iterable[Optional[Hashable]],
               include_first: bool = False,
               include_last: bool = False,
               include_all: bool = False) -> Dict[int, Hashable]:
    if include_all:
        return {ii: x for ii, x in enumerate(state) if x is not None}

    ret = {}
    if include_last:
        last_item = next(x for x in list(state) if x is not None)
        last_idx = list(state).index(last_item)
        ret[last_idx] = last_item

    if include_first:
        first_item = next(x for x in reversed(list(state)) if x is not None)
        first_idx = list(state).index(first_item)
        ret[first_idx] = first_item

    return ret

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
    def __init__(self, requested, pos, state):
        msg = f"Item <{requested}> requested to be added to pos {pos}, but there is no room: <{state}>"
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
    def _remove_items(cls,
                      state: Iterable[Optional[Hashable]],
                      removed: Iterable[Hashable] = None) -> List[Optional[Hashable]]:
        if removed is None:
            return list(state)

        new_state = [x for x in state]

        for item in removed:
            idx = list(state).index(item)
            if idx is None:
                raise ItemNotFoundToRemoveException(requested=item, state=new_state)

            available = cls.get_removeable(new_state)
            if item not in available.values():
                raise ItemNotAccessibleToRemoveException(requested=item, state=new_state, available=available)

            new_state[idx] = None
            new_state = cls.post_process(new_state)
        return new_state

    @classmethod
    def _add_items(cls,
                   state: Iterable[Optional[Hashable]],
                   added: Iterable[Hashable] = None,
                   allow_replacement: bool = False
                   ) -> List[Optional[Hashable]]:
        if added is None:
            return list(state)

        new_state = [x for x in state]

        for item in added:
            idx = cls.get_addable_positions(state)[0]
            '''Check if there is space in the channel'''
            if not allow_replacement and len([x for x in new_state if x is not None]) + 1 > len(new_state):
                raise NoRoomToAddException(requested=item, pos=idx, state=new_state)
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

        return new_state

    @classmethod
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
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
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return accessible(state=state, include_all=True)

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
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return accessible(state=state, include_all=True)

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
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return accessible(state=state, include_all=True)

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
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return accessible(state=state, include_first=True)

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
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return accessible(state=state, include_first=True)

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
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return accessible(state=state, include_last=True)


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
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return accessible(state=state, include_last=True)

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
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return accessible(state=state, include_first=True, include_last=True)

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
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return accessible(state=state, include_first=True, include_last=True)

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
    def get_removeable(cls, state: Iterable[Optional[Hashable]]) -> Dict[int, Hashable]:
        return accessible(state=state, include_first=True, include_last=True)

    @classmethod
    def get_addable_positions(cls, state: Iterable[Optional[Hashable]]) -> List[int]:
        return [0] if state[0] is None else []

    @classmethod
    def post_process(cls, state: Iterable[Optional[Hashable]]) -> List[Hashable]:
        return flow(state, backwards=True)




if __name__ == "__main__":
    from pprint import pprint
    def test_allavail_1():
        state = [None for ii in range(5)]
        cp = AllAvailableChannelProcessor()
        state = cp.process(state, added={2: 'a', 3: 'b'})
        pprint(state)

        state = cp.process(state, added={1: 'c', 4: 'd'})
        pprint(state)

        state = cp.process(state, removed={1: 'c', 2: 'a'})
        pprint(state)


        state = cp.process(state, removed={1: 'c', 2: 'a'})
        pprint(state)

    def test_fifo_1():
        state = [None for ii in range(5)]

        cp = FIFOFlowChannelProcessor()
        new_state = cp.process(state=state,
                   added={0:'a'})

        pprint(new_state)

        new_state = cp.process(state=new_state,
                   added={0:'b'})

        pprint(new_state)
        new_state = cp.process(state=new_state,
                   added={0:'c'})

        pprint(new_state)
        new_state = cp.process(state=new_state,
                   added={0:'d'})

        pprint(new_state)
        new_state = cp.process(state=new_state,
                   added={0:'e'})
        new_state = cp.process(state=new_state,
                               added={0: 'f'})

        pprint(new_state)

        new_state = cp.process(state=new_state,
                               removed={4: 'a'})

        pprint(new_state)

    def test_lifo_1():
        state = [None for ii in range(5)]

        cp = LIFOFlowChannelProcessor()
        new_state = cp.process(state=state,
                   added={0:'a'})

        pprint(new_state)

        new_state = cp.process(state=new_state,
                   added={0:'b'})

        pprint(new_state)
        new_state = cp.process(state=new_state,
                   added={0:'c'})

        pprint(new_state)
        new_state = cp.process(state=new_state,
                   added={0:'d'})

        pprint(new_state)
        new_state = cp.process(state=new_state,
                   added={0:'e'})

        pprint(new_state)

        new_state = cp.process(state=new_state,
                               removed={0: 'e'})

        pprint(new_state)


    test_fifo_1()
    test_lifo_1()