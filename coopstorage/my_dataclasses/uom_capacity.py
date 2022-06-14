from dataclasses import dataclass
from coopstorage.my_dataclasses import UoM


@dataclass(frozen=True, slots=True)
class UoMCapacity:
    uom: UoM
    capacity: float

    def as_dict(self):
        return {
            'uom': self.uom.as_dict(),
            'capacity': self.capacity
        }