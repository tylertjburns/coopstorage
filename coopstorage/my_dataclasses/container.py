from dataclasses import dataclass, field
from typing import List, Callable, Any
from coopstorage.my_dataclasses import Content, UoM, UoMCapacity
from cooptools.randoms import a_string
from datetime import datetime

@dataclass(frozen=True, slots=True)
class Container:
    lpn: str
    uom: UoM
    uom_capacities: frozenset[UoMCapacity] = field(default_factory=frozenset)
    contents: List[Content] = None
    content_codes: List[str] = None
    parent_container: Any = None
    init_datestamp: datetime = field(init=False)

    def __post_init__(self):
        if self.contents is None: object.__setattr__(self, 'contents', [])
        if self.content_codes is None: object.__setattr__(self, 'content_codes', [])
        object.__setattr__(self, 'init_datestamp', datetime.now())

    def __hash__(self):
        return self.lpn

    @property
    def UoM(self):
        return self.uom

def container_factory(container: Container = None,
                      lpn: str = None,
                      uom: UoM = None,
                      uom_capacities: List[UoMCapacity] = None,
                      contents: List[Content] = None,
                      content_codes: List[str] = None,
                      parent_container: Container = None,
                      naming_provider: Callable[[], str] = None,
                      string_naming_kwargs=None):

    lpn = lpn or \
          (naming_provider() if naming_provider else None) \
          or (container.lpn if container else None) \
          or a_string(**string_naming_kwargs)

    uom = uom or (container.uom if container else None)
    uom_capacities = uom_capacities or (container.uom_capacities if container else None)
    contents = contents or (container.contents if container else None)
    content_codes = content_codes or (container.content_codes if container else None)
    parent = parent_container or (container.parent_container if container else None)

    return Container(
        lpn=lpn,
        uom=uom,
        uom_capacities=uom_capacities,
        contents=contents,
        content_codes=content_codes,
        parent_container=parent
    )
