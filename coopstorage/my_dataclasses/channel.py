import uuid
from coopstorage.enums import ChannelType
from cooptools.commandDesignPattern import CommandController, CommandProtocol
from dataclasses import dataclass, field
from typing import List, Generic, TypeVar
import logging

T = TypeVar("T")
logger = logging.getLogger("coopstorage.channels")

@dataclass(frozen=True, slots=True)
class ChannelState(Generic[T]):
    content: List = field(default_factory=list)

    def extractable_content(self, channel_type: ChannelType) -> List[T]:
        if len(self.content) == 0:
            return []
        elif channel_type == ChannelType.ALL_ACCESSIBLE:
            return self.content
        elif channel_type == ChannelType.FIFO_QUEUE:
            return [self.content[0]]
        elif channel_type == ChannelType.LIFO_QUEUE:
            return [self.content[-1]]
        else:
            raise NotImplementedError(f"No implementation for {channel_type}")

@dataclass(frozen=True)
class ChannelMeta:
    id: str | uuid.UUID
    channel_type: ChannelType
    capacity: int

    def __hash__(self):
        return hash(self.id)

    def with_update(self,
                    id: str | uuid.UUID = None,
                    channel_type: ChannelType = None,
                    capacity: int = None
                    ):
        return ChannelMeta(
            id=id if id is not None else self.id,
            channel_type=channel_type if channel_type is not None else self.channel_type,
            capacity=capacity if capacity is not None else self.capacity
        )

    def to_payload(self):
        return {
            'id': self.id,
            'channel_type': self.channel_type.value,
            'capacity': self.capacity
        }

def add_to_channel(id: str | uuid.UUID,
                   state: ChannelState,
                   capacity: int,
                   to_add: List[T]) -> ChannelState:
    logger.debug(f"Adding content to channel [{id}]: {to_add}")
    # Verify the amount of additional content will fit
    if len(state.content) + len(to_add) > capacity:
        raise NoCapacityChannelException(
                channel_id=id,
                capacity=capacity,
                current_state=state,
                requested_to_add=to_add
        )

    state = ChannelState(
        content=state.content + to_add
    )
    logger.debug(f"New channel state for [{id}]: {state}")

    return state


def remove_from_channel(id: str | uuid.UUID,
                        state: ChannelState,
                        channel_type:ChannelType,
                        to_remove: List[T]) -> ChannelState:
    logger.debug(f"Removing content from channel [{id}]: {to_remove}")

    # Verify content is in the channel
    if not all(x in state.content for x in to_remove):
        raise ContentNotInChannelException(
                channel_id=id,
                missing=[x for x in to_remove if x not in state.content],
                current_state=state,
                requested_to_remove=to_remove
        )


    # Verify removal of the content
    working_state = state
    for x in to_remove:
        # Verify the content is in position
        if x not in working_state.extractable_content(channel_type=channel_type):
            raise ContentNotExtractableChannelException(
                    channel_id=id,
                    channel_type=channel_type,
                    current_state=state,
                    requested_to_remove=to_remove
                )

        new_content = working_state.content
        new_content.remove(x)
        working_state = ChannelState(
            content=new_content
        )

    logger.debug(f"New channel state for [{id}]: {state}")
    return working_state


class ChannelProcessor(Generic[T]):
    def __init__(self,
                 meta: ChannelMeta,
                 command_cache_interval: int = 25
                 ):
        self.meta: ChannelMeta = meta
        self._command_controller: CommandController = CommandController(init_state=ChannelState(),
                                                                        cache_interval=command_cache_interval)

    def undo(self):
        return self._command_controller.undo()

    def redo(self):
        return self._command_controller.redo()

    @property
    def ExtractableContent(self):
        return self._command_controller.State.extractable_content(self.meta.channel_type)

    @property
    def State(self) ->ChannelState:
        return self._command_controller.State


    def add(self, to_add: List[T]) -> ChannelState:
        logger.info(f"Adding content to channel [{self.meta.id}]: {to_add}")
        updated = self._command_controller.execute(
            commands=[AddContentToChannelCommand(
                channel_processor=self,
                to_add=to_add)]
        )
        logger.info(f"New channel state for [{self.meta.id}]: {updated}")
        return updated

    def remove(self, to_remove: List[T]) -> ChannelState:
        logger.info(f"Removing content from channel [{self.meta.id}]: {to_remove}")
        updated = self._command_controller.execute(
            commands=[RemoveContentFromChannelCommand(
                channel_processor=self,
                to_remove=to_remove)]
        )

        logger.info(f"New channel state for [{self.meta.id}]: {updated}")
        return updated


class BaseException(Exception):
    def __init__(self):
        logger.error(self.msg())
        super().__init__(self.msg())

    def msg(self):
        raise NotImplementedError()

@dataclass
class NoCapacityChannelException(BaseException):
    def __init__(self,
        channel_id: str | uuid.UUID,
        capacity: int,
        current_state: ChannelState,
        requested_to_add: List[T]
    ):
        self.channel_id: str | uuid.UUID = channel_id
        self.capacity: int = capacity
        self.current_state: ChannelState = current_state
        self.requested_to_add: List[T] = requested_to_add
        super().__init__()

    def msg(self):
        return f"{self.requested_to_add} was requested to be added to channel {self.channel_id} but cannot fit due to capacity [{self.capacity}]. Current content: {self.current_state.content}"


@dataclass
class ContentNotExtractableChannelException(BaseException):
    def __init__(self,
            channel_id: str | uuid.UUID,
            channel_type: ChannelType,
            current_state: ChannelState,
            requested_to_remove: List[T]
    ):
        self.channel_id: str | uuid.UUID = channel_id
        self.channel_type: ChannelType = channel_type
        self.current_state: ChannelState = current_state
        self.requested_to_remove: List[T] = requested_to_remove
        super().__init__()

    def msg(self):
        return f"{self.requested_to_remove} was requested to be removed from the channel {self.channel_id} but cannot remove in order for [{self.channel_type.name}]. Current content: {self.current_state.content}"

@dataclass
class ContentNotInChannelException(BaseException):
    def __init__(self,
            channel_id: str | uuid.UUID,
            current_state: ChannelState,
            requested_to_remove: List[T],
            missing: List[T]
    ):
        self.channel_id: str | uuid.UUID=channel_id
        self.current_state: ChannelState=current_state
        self.requested_to_remove: List[T]=requested_to_remove
        self.missing: List[T]=missing
        super().__init__()

    def msg(self):
        return f"{self.requested_to_remove} was requested to be removed from the channel {self.channel_id} but requested is not in channel {self.missing}. Current content: {self.current_state.content}"


@dataclass(frozen=True)
class AddContentToChannelCommand(CommandProtocol):
    channel_processor: ChannelProcessor
    to_add: List[T]

    def execute(self, state: ChannelState) -> ChannelState:
        return add_to_channel(
            id=self.channel_processor.meta.id,
            state=state,
            capacity=self.channel_processor.meta.capacity,
            to_add=self.to_add
        )

@dataclass(frozen=True)
class RemoveContentFromChannelCommand(CommandProtocol):
    channel_processor: ChannelProcessor
    to_remove: List[T]

    def execute(self, state: ChannelState) -> ChannelState:
        return remove_from_channel(
            id=self.channel_processor.meta.id,
            state=state,
            channel_type=self.channel_processor.meta.channel_type,
            to_remove=self.to_remove
        )

if __name__ == "__main__":
    from cooptools.randoms import LETTERS
    logging.basicConfig(level=logging.INFO)
    cp = ChannelProcessor(
        meta=ChannelMeta(
            id="c1",
            channel_type=ChannelType.ALL_ACCESSIBLE,
            capacity=5
        )
    )

    for x in range(7):
        try:
            cp.add([LETTERS[x]])
        except NoCapacityChannelException as e:
            logger.error(f"DO SOME ERROR HANDLING")
            break

    for x in ['a', 'c', 'e', 'g']:
        try:
            cp.remove([x])
        except ContentNotInChannelException:
            logger.error(f"DO SOME ERROR HANDLING")
            break

    print(cp.State)
    cp.undo()
    print(cp.State)
    cp.redo()
    print(cp.State)
    cp.undo()
    cp.undo()
    print(cp.State)


