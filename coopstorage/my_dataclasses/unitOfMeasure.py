import uuid
from dataclasses import dataclass
from typing import Tuple



@dataclass(frozen=True, slots=True)
class UnitOfMeasure:
    name: str
    each_qty: float = 1
    dimensions: Tuple[float,float,float] = None
    nesting_factor: Tuple[float, float, float] = None
    max_stack: int = 1

    def as_dict(self):
        return {
            'name': self.name
        }

def uom_factory(uom: UnitOfMeasure = None,
                name: str = None,
                each_qty: float = None,
                dimensions: Tuple[float, float, float] = None,
                nesting_factor: Tuple[float, float, float] = None,
                max_stack: int = None
                ) -> UnitOfMeasure:
    name = name or (uom.name if uom else None) or uuid.uuid4()
    each_qty = each_qty or (uom.each_qty if uom else None)
    dimensions = dimensions or (uom.dimensions if uom else None)
    nesting_factor = nesting_factor or (uom.nesting_factor if uom else None)
    max_stack = (max_stack if (max_stack or max_stack == 0) else None) or (uom.max_stack if uom else None)

    return UnitOfMeasure(name=name,
                         each_qty=each_qty,
                         dimensions=dimensions,
                         nesting_factor=nesting_factor,
                         max_stack=max_stack)