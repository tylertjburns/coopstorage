import unittest
import coopstorage as ssm
from coopstorage.my_dataclasses import StorageState, UoMCapacity, loc_inv_state_factory, content_factory
import coopstorage.uom_manifest as uoms
import tests.sku_manifest as skus
from coopstorage.exceptions import *

class Test_StorageStateMutations(unittest.TestCase):

    def test__create_a_storage_state(self):
        # arrange
        n_locs = 5
        loc_inv_states = frozenset([loc_inv_state_factory() for x in range(n_locs)])

        # act
        state = StorageState(
            loc_states=loc_inv_states
        )

        # assert
        self.assertEqual(state.loc_states, loc_inv_states)
        self.assertEqual(state.Locations, [x.location for x in loc_inv_states])
        self.assertEqual(state.EmptyLocs, state.Locations)
        self.assertEqual(state.OccupiedLocs, [])
        self.assertEqual(len(state.Inventory), len(state.Locations))

    def test__add_content(self):
        # arrange
        n_locs = 5
        qty_capacity = 10
        qty_to_add = 1
        loc_inv_states = frozenset([loc_inv_state_factory(
            loc_uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=qty_capacity)])) for x in range(n_locs)])

        state = StorageState(
            loc_states=loc_inv_states
        )
        content = content_factory(resource=skus.sku_a, uom=uoms.each, qty=qty_to_add)


        # act
        new = ssm.add_content(storage_state=state, to_add=content)

        #assert
        self.assertEqual(new.qty_of_resource_uoms([content.resourceUoM])[content.resourceUoM], qty_to_add)

    def test__add_content__doesnt_fit_in_one_place(self):
        # arrange
        n_locs = 5
        qty_capacity = 10
        qty_to_add = 15
        loc_inv_states = frozenset([loc_inv_state_factory(
            loc_uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=qty_capacity)])) for x in range(n_locs)])

        state = StorageState(
            loc_states=loc_inv_states
        )
        content = content_factory(resource=skus.sku_a, uom=uoms.each, qty=qty_to_add)


        # act
        actor = lambda: ssm.add_content(storage_state=state, to_add=content)

        #assert
        self.assertRaises(NoLocationWithCapacityException, actor)

    def test__add_content__multiple_adds(self):
        # arrange
        n_locs = 5
        qty_capacity = 10
        qty_to_add = 7
        loc_inv_states = frozenset([loc_inv_state_factory(
            loc_uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=qty_capacity)])) for x in range(n_locs)])

        state = StorageState(
            loc_states=loc_inv_states
        )
        content = content_factory(resource=skus.sku_a, uom=uoms.each, qty=qty_to_add)
        new = ssm.add_content(storage_state=state, to_add=content)

        # act
        new2 = ssm.add_content(storage_state=new, to_add=content)

        #assert
        self.assertEqual(new2.qty_of_resource_uoms([content.resourceUoM])[content.resourceUoM], qty_to_add * 2)

    def test__remove_content(self):
        # arrange
        n_locs = 5
        qty_capacity = 10
        qty_to_add = 7
        qty_to_remove = 3
        loc_inv_states = frozenset([loc_inv_state_factory(
            loc_uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=qty_capacity)])) for x in range(n_locs)])

        state = StorageState(
            loc_states=loc_inv_states
        )
        content = content_factory(resource=skus.sku_a, uom=uoms.each, qty=qty_to_add)
        to_remove = content_factory(resource=skus.sku_a, uom=uoms.each, qty=qty_to_remove)

        new = ssm.add_content(storage_state=state, to_add=content)
        new = ssm.add_content(storage_state=new, to_add=content)

        # act
        post = ssm.remove_content(storage_state=new, to_remove=to_remove)

        #assert
        self.assertEqual(post.qty_of_resource_uoms([content.resourceUoM])[content.resourceUoM], qty_to_add * 2 - qty_to_remove)

    def test__remove_content__no_single_location(self):
        # arrange
        n_locs = 5
        qty_capacity = 10
        qty_to_add = 7
        qty_to_remove = 8
        loc_inv_states = frozenset([loc_inv_state_factory(
            loc_uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=qty_capacity)])) for x in range(n_locs)])

        state = StorageState(
            loc_states=loc_inv_states
        )
        content = content_factory(resource=skus.sku_a, uom=uoms.each, qty=qty_to_add)
        to_remove = content_factory(resource=skus.sku_a, uom=uoms.each, qty=qty_to_remove)

        new = ssm.add_content(storage_state=state, to_add=content)
        new = ssm.add_content(storage_state=new, to_add=content)

        # act
        actor = lambda: ssm.remove_content(storage_state=new, to_remove=to_remove)

        #assert
        self.assertRaises(NoLocationToRemoveContentException, actor)


