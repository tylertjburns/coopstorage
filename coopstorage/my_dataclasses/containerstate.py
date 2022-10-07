from dataclasses import dataclass, field, asdict
from typing import List, Callable, Any, Dict
from coopstorage.my_dataclasses import Content, UnitOfMeasure, UoMCapacity, ResourceUoM
from cooptools.randoms import a_string
from datetime import datetime
from json import dumps

@dataclass(frozen=True, slots=True)
class ContainerState:
    lpn: str
    uom: UnitOfMeasure
    uom_capacities: frozenset[UoMCapacity] = field(default_factory=frozenset)
    contents: frozenset[Content] = None
    content_codes: frozenset[str] = None
    init_datestamp: datetime = field(init=False)

    def __post_init__(self):
        if self.contents is None: object.__setattr__(self, 'contents', [])
        if self.content_codes is None: object.__setattr__(self, 'content_codes', [])

        object.__setattr__(self, 'init_datestamp', datetime.now())

    def __hash__(self):
        return hash(self.lpn)

    def as_dict(self):
        return {
            f'{self.lpn=}'.split('=')[0].replace('self.', ''): self.lpn,
            f'{self.uom=}'.split('=')[0].replace('self.', ''): self.uom.as_dict(),
            f'{self.uom_capacities=}'.split('=')[0].replace('self.', ''): [x.as_dict() for x in self.uom_capacities],
            f'{self.contents=}'.split('=')[0].replace('self.', ''): [x.as_dict() for x in self.contents] if self.contents else [],
            f'{self.content_codes=}'.split('=')[0].replace('self.', ''): list(self.content_codes) if self.content_codes else [],
            f'{self.init_datestamp=}'.split('=')[0].replace('self.', ''): str(self.init_datestamp)
        }

    @property
    def UoM(self):
        return self.uom

    @property
    def QtyResourceUoMs(self) -> Dict[ResourceUoM, float]:
        ret = {}
        # accumulate the qty of resource uoms
        for c in self.contents:
            ret.setdefault(c.resourceUoM, 0)
            ret[c.resourceUoM] += c.qty

        return ret

    @property
    def QtyUoMs(self) -> Dict[UnitOfMeasure, float]:
        ret = {}
        # accumulate the qty of resource uoms
        for c in self.contents:
            ret.setdefault(c.UoM, 0)
            ret[c.UoM] += c.qty

        return ret

    @property
    def UoMCapacities(self) -> Dict[UnitOfMeasure, float]:
        return {x.uom: x.capacity for x in self.uom_capacities}

    @property
    def SpaceForUoMs(self) -> Dict[UnitOfMeasure, float]:
        capacities = self.UoMCapacities
        qty_uoms = self.QtyUoMs

        return {uom: capacities[uom] - qty_uoms.get(uom, 0) for uom, _ in capacities.items()}

def container_factory(container: ContainerState = None,
                      lpn: str = None,
                      uom: UnitOfMeasure = None,
                      uom_capacities: frozenset[UoMCapacity] = None,
                      contents: frozenset[Content] = None,
                      content_codes: frozenset[str] = None,
                      parent_container: ContainerState = None,
                      naming_provider: Callable[[], str] = None,
                      string_naming_kwargs=None):

    lpn = lpn or \
          (naming_provider() if naming_provider else None) \
          or (container.lpn if container else None) \
          or a_string(**string_naming_kwargs)

    uom = uom if uom is not None else (container.uom if container else None)
    uom_capacities = uom_capacities if uom_capacities is not None else (container.uom_capacities if container else None)
    contents = contents if contents is not None else (container.contents if container else None)
    content_codes = content_codes if content_codes is not None else (container.content_codes if container else None)

    return ContainerState(
        lpn=lpn,
        uom=uom,
        uom_capacities=uom_capacities,
        contents=contents,
        content_codes=content_codes,
    )


if __name__ == "__main__":
    from coopstorage.uom_manifest import bottle
    from pprint import pprint

    cnt = ContainerState(lpn='Test', uom=bottle)
    pprint(cnt.as_dict())