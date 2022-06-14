import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UoM:
    name: str

    def as_dict(self):
        return {
            'name': self.name
        }

def uom_factory(uom: UoM = None,
                name: str = None) -> UoM:
    name = name or (uom.name if uom else None) or uuid.uuid4()

    return UoM(name=name)