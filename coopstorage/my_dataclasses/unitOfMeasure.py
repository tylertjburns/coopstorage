import uuid
from dataclasses import dataclass

@dataclass(frozen=True)
class UoM:
    name: str

def uom_factory(uom: UoM = None,
                name: str = None) -> UoM:
    name = name or (uom.name if uom else None) or uuid.uuid4()

    return UoM(name=name)