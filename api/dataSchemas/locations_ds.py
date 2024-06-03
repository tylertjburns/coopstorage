import pydantic
from dataclasses import dataclass
from coopstorage.my_dataclasses.location import Location
from typing import List
from api.utils import convert_flat_dataclass_to_pydantic
from pydantic import Field
# class LocationSchemaConfig:
#     allow_population_by_field_name = True
#     schema_extra = {
#         "example": {
#             "locations": [
#                 Location(id='a').as_dict(),
#                 Location(id='b').as_dict(),
#                 Location(id='c').as_dict()
#             ]
#         }
#     }
#

# PydanticLocation = convert_flat_dataclass_to_pydantic(Location)
#
# def get_pyd_loc_from_loc(loc: Location) -> PydanticLocation:
#     dic = asdict(loc)
#     print(dic)
#     return PydanticLocation(**dic)
#
@dataclass
class LocationsSchema():
    locations: List[Location]


if __name__ =="__main__":
    # print(Location().__dict__)

    data = {
      "locations": [
        {
          "id": "string",
          "uom_capacities": [
            {
              "uom": {
                "name": "string",
                "each_qty": 1,
                "dimensions": [
                  None,
                  None,
                  None
                ],
                "nesting_factor": [
                  None,
                  None,
                  None
                ],
                "max_stack": 1
              },
              "capacity": 0
            }
          ],
          "resource_limitations": [
            {
              "name": "string",
              "type": 1,
              "description": "string"
            }
          ],
          "coords": [
            0
          ],
          "channel_type": 1,
          "max_resources_uoms": 1
        }
      ]
    }


    schem = LocationsSchema(locations=[Location(**x) for x in data['locations']])

    print(schem)