from cooptools.commandDesignPattern import CommandController, CommandProtocol
from dataclasses import dataclass, field
from coopstorage import StorageState, Location, Resource, UoMCapacity, ContainerState, location_prioritizer, LocInvState
from coopstorage import storage_state_mutations as ssm
from typing import List

@dataclass
class AddLocationsCommand(CommandProtocol):
    locations: List[Location]

    def execute(self, state: StorageState) -> StorageState:
        return ssm.add_locations(state, locations=self.locations)


@dataclass
class RemoveLocationsCommand(CommandProtocol):
    locations: List[Location]

    def execute(self, state: StorageState) -> StorageState:
        return ssm.remove_locations(state, locations=self.locations)

@dataclass
class AddContainerToStorageCommand(CommandProtocol):
    container: ContainerState
    location: Location = None
    loc_prioritizer: location_prioritizer = None


    def execute(self, state: StorageState) -> StorageState:
        return ssm.add_content(
            storage_state=state,
            to_add=self.container,
            location=self.location,
            loc_prioritizer=self.loc_prioritizer
        )


@dataclass
class RemoveContainerFromStorageCommand(CommandProtocol):
    container: ContainerState

    def execute(self, state: StorageState) -> StorageState:
        return ssm.remove_content(
            storage_state=state,
            to_remove=self.container
        )

@dataclass
class AdjustLocationInStorageCommand(CommandProtocol):
    location: Location
    added_resources: List[Resource] = None,
    removed_resources: List[Resource] = None,
    added_uom_capacities: List[UoMCapacity] = None,
    removed_uom_capacities: List[UoMCapacity] = None

    def execute(self, state: StorageState) -> StorageState:
        return ssm.adjust_location(state,
                                   location=self.location,
                                   added_resources=self.added_resources,
                                   removed_resources=self.removed_resources,
                                   added_uom_capacities=self.added_uom_capacities,
                                   removed_uom_capacities=self.removed_uom_capacities)

