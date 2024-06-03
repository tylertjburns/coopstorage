from cooptools.commandDesignPattern import CommandController, CommandProtocol
from dataclasses import dataclass
from coopstorage.storage import Location, ContainerState, LocInvState
from coopstorage.storage import loc_inv_state_mutations as lism

@dataclass
class AddContainerToLocationCommand(CommandProtocol):
    container: ContainerState
    location: Location

    def execute(self, state: LocInvState) -> LocInvState:
        return lism.add_container_to_location(state, self.container)


@dataclass
class RemoveContainerFromLocationCommand(CommandProtocol):
    container: ContainerState
    location: Location

    def execute(self, state: LocInvState) -> LocInvState:
        return lism.remove_container_from_location(state, self.container)