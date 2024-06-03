from pydantic.dataclasses import dataclass as pydandataclass
from coopstorage.my_dataclasses.unitOfMeasure import UnitOfMeasure

class UnitOfMeasureSchemaConfig:
    allow_population_by_field_name = True
    schema_extra = {
        "example": {
        }
    }

@pydandataclass(config=UnitOfMeasureSchemaConfig)
class UnitOfMeasureSchema:
    uom: UnitOfMeasure
