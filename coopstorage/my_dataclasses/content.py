import uuid
from dataclasses import dataclass, field
from coopstorage.my_dataclasses import Resource, ResourceUoM, ResourceType, UnitOfMeasure, resourceUom_factory, resource_factory, uom_factory, UoMCapacity
from typing import List, Tuple
import random as rnd

class ContentFactoryException(Exception):
    def __init__(self):
        super().__init__(str(type(self)))


@dataclass(frozen=True, slots=True)
class Content:
    resourceUoM: ResourceUoM
    qty: float
    id: str = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'id', uuid.uuid4())
        if self.qty < 0:
            raise ValueError(f"qty cannot be zero, {self.qty} provided")

    def match_resouce_uom(self, content):
        return content.Resource == self.Resource and content.UnitOfMeasure == self.UoM

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"C({self.Resource.name}, {self.UoM.name}, {self.qty}) [{self.id}]"

    def as_dict(self):
        return {
            'id': str(self.id),
            'resource_uom': self.resourceUoM.as_dict(),
            'qty': self.qty
        }

    @property
    def Resource(self) -> Resource:
        return self.resourceUoM.resource

    @property
    def UoM(self) -> UnitOfMeasure:
        return self.resourceUoM.uom

    @property
    def CapacityRequired(self) -> UoMCapacity:
        return UoMCapacity(uom=self.UoM, capacity=self.qty)

def content_factory(content: Content = None,
                    resource_uom: ResourceUoM = None,
                    resource: Resource = None,
                    resource_name: str = None,
                    resource_description: str = None,
                    resource_type: ResourceType = None,
                    uom: UnitOfMeasure = None,
                    uom_name: str = None,
                    qty: float = None,
                    rnd_qty_range: Tuple[int, int] = None
                    ) -> Content:

    resource_lmb = lambda: resource or \
                           (resource_uom.resource if resource_uom else None) or \
                           (content.resourceUoM.resource if content else None) or \
                           resource_factory(resource=resource,
                                            name=resource_name,
                                            description=resource_description,
                                            type=resource_type)

    uom_lmb = lambda: uom or \
                      (resource_uom.uom if resource_uom else None) or \
                      (content.resourceUoM.uom if content else None) or \
                      uom_factory(name=uom_name)

    resource_uom = resource_uom or \
                   (content.resourceUoM if content else None) or \
                    resourceUom_factory(resource_uom=resource_uom,
                                       resource=resource_lmb(),
                                       uom=uom_lmb())

    qty = qty or \
          (content.qty if content else None) or \
          (rnd.randint(rnd_qty_range[0], rnd_qty_range[1]) if rnd_qty_range else None) \
          or 0

    content = Content(
        resourceUoM=resource_uom,
        qty=qty,
    )

    return content

def merge_content(content_list: List[Content]) -> List[Content]:
    content_by_ru = {}
    for content in content_list:
        content_by_ru.setdefault(content.resourceUoM, [])
        content_by_ru[content.resourceUoM].append(content)

    ret = []
    for ru, c_list in content_by_ru.items():
        ret.append(content_factory(c_list[0], qty=sum(x.qty for x in c_list)))

    return ret