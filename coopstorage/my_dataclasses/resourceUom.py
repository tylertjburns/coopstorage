from dataclasses import dataclass
from coopstorage.my_dataclasses import Resource, UoM, resource_factory, uom_factory

@dataclass(frozen=True)
class ResourceUoM:
    resource: Resource
    uom: UoM

def resourceUom_factory(resource_uom: ResourceUoM = None,
                        resource: Resource = None,
                        uom: UoM = None) -> ResourceUoM:
    resource = resource or (resource_uom.resource if resource_uom else None) or resource_factory()
    uom = uom or (resource_uom.uom if resource_uom else None) or uom_factory()

    return ResourceUoM(
        resource=resource,
        uom=uom
    )