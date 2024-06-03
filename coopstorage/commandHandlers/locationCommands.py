from cooptools.commandDesignPattern import CommandController, CommandProtocol
from dataclasses import dataclass
from coopstorage import Location, Resource, UoMCapacity
from coopstorage.storage import loc_state_mutations as lsm
from typing import List

@dataclass
class AddResourceLimitationsToLocationCommand(CommandProtocol):
    added_resources: List[Resource]

    def execute(self, state: Location) -> Location:
        return lsm.adjust_location(location=state,
                                   new_resource_limitations=self.added_resources)

@dataclass
class RemoveResourceLimitationsToLocationCommand(CommandProtocol):
    removed_resources: List[Resource]

    def execute(self, state: Location) -> Location:
        return lsm.adjust_location(location=state,
                                   removed_resource_limitations=self.removed_resources)


@dataclass
class AddUomCapacitiesToLocationCommand(CommandProtocol):
    added_uom_capacities: List[UoMCapacity]

    def execute(self, state: Location) -> Location:
        return lsm.adjust_location(location=state,
                                   added_uom_capacities=self.added_uom_capacities)


@dataclass
class RemoveUomCapacitiesFromLocationCommand(CommandProtocol):
    removed_uom_capacities: List[UoMCapacity]

    def execute(self, state: Location) -> Location:
        return lsm.adjust_location(location=state,
                                   removed_uom_capacities=self.removed_uom_capacities)