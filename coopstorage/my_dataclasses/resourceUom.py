from dataclasses import dataclass
from coopstorage.my_dataclasses import Resource, UnitOfMeasure, resource_factory, uom_factory, ResourceType


# @dataclass(frozen=True, slots=True) #pydantic doesnt support slots
@dataclass(frozen=True)
class ResourceUoM:
    resource: Resource
    uom: UnitOfMeasure

    def as_dict(self):
        return {
            'resource': self.resource.as_dict(),
            'uom': self.uom.as_dict()
        }

def resourceUom_factory(resource_uom: ResourceUoM = None,
                        resource: Resource = None,
                        resource_name: str = None,
                        resource_description: str = None,
                        resource_type: ResourceType = None,
                        uom: UnitOfMeasure = None,
                        uom_name: str = None) -> ResourceUoM:
    resource = resource or \
               (resource_uom.resource if resource_uom is not None else None) or \
               resource_factory(name=resource_name,
                                 description=resource_description,
                                 type=resource_type)

    uom = uom or (resource_uom.uom if resource_uom else None) or uom_factory(name=uom_name)

    return ResourceUoM(
        resource=resource,
        uom=uom
    )