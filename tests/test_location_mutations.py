import unittest
from coopstorage.my_dataclasses import Location
import tests.sku_manifest as skus
import tests.uom_manifest as uoms

class Test_LocationMutations(unittest.TestCase):

    def test__create__with_des(self):
        # arrange
        capacity = frozenset([x for x in uoms.uoms])

        # act
        test_loc = Location(id='Test', uom_capacities=capacity)

        # assert
        self.assertEqual(test_loc.uom_capacities,capacity)
