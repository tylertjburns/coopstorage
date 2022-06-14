from dataclasses import dataclass
from cooptools.coopEnum import CoopEnum
from cooptools.randoms import a_phrase
import uuid
from enum import auto


class ResourceType(CoopEnum):
    DEFAULT = auto()


@dataclass(frozen=True, slots=True)
class Resource:
    name: str
    description: str
    type: ResourceType

    def __hash__(self):
        return hash((self.name, self.type))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def as_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'type': self.type.name
        }

def resource_factory(resource: Resource = None,
                     name: str = None,
                     description: str = None,
                     type: ResourceType = None) -> Resource:

    new_name = name or (resource.name if resource else None) or uuid.uuid4()
    new_desc = description or (resource.description if resource else None) or a_phrase()
    new_type = type or (resource.type if resource else None) or ResourceType.random()

    return Resource(
        name=new_name,
        description=new_desc,
        type=new_type
    )

