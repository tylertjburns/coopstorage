import unittest
from coopstorage.my_dataclasses import LocInvState, Location, Content, ResourceUoM, UoMCapacity, content_factory, loc_inv_state_factory
import coopstorage as ssm
import tests.sku_manifest as skus
import coopstorage.uom_manifest as uoms
from coopstorage.exceptions import *
from coopstorage.enums import ChannelType

class TestLocInvStateMutations(unittest.TestCase):

    def test__create_state__empty(self):
        # arrange
        test_loc = Location(id='Test')

        # act
        state = LocInvState(
            location=test_loc
        )

        # assert
        self.assertEqual(state.location,test_loc)
        self.assertEqual(state.location.uom_capacities, frozenset())
        self.assertEqual(state.ActiveUoMDesignations, [])

    def test__create_state__with_des(self):
        # arrange
        test_loc = Location(id='Test', uom_capacities=frozenset([x for x in uoms.manifest]))

        # act
        state = LocInvState(
            location=test_loc
        )

        # assert
        self.assertEqual(state.location,test_loc)
        self.assertEqual(state.ActiveUoMDesignations, [])

    def test__create_state__with_cont(self):
        # arrange
        test_loc = Location(id='Test')
        ru=ResourceUoM(resource=skus.sku_a, uom=uoms.each)
        qty = 10
        content = Content(
            resourceUoM=ru,
            qty=qty
        )

        # act
        state = LocInvState(
            location=test_loc,
            contents=frozenset([content])
        )

        # assert
        self.assertEqual(state.location,test_loc)
        self.assertEqual(len(state.containers), 1)
        self.assertEqual(state.qty_resource_uom(resource_uom=ru), qty)
        self.assertEqual(state.ActiveUoMDesignations, [uoms.each])

    def test__mutate_state__add_content_same_ru__will_fit(self):
        #arrange
        qty=20
        uom_name = 'Each'
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, qty)]),
                                      contents=frozenset([content_factory(resource=skus.sku_a, qty=qty/2, uom=uoms.each)]),)
        new_content = content_factory(resource=skus.sku_a, qty=qty/2, uom=uoms.each)

        # act
        new = ssm.add_content_to_loc(inv_state=state, content=new_content)

        # assert
        self.assertEqual(len(new.containers), len(state.containers))
        self.assertEqual(new.qty_resource_uom(new_content.resourceUoM), state.qty_resource_uom(new_content.resourceUoM) + new_content.qty)

    def test__mutate_state__add_content_same_ru__will_not_fit(self):
        #arrange
        qty=20
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, qty)]),
                                      contents=frozenset([content_factory(resource=skus.sku_a, qty=qty/2, uom=uoms.each)]),)
        new_content = content_factory(resource=skus.sku_a, qty=qty, uom=uoms.each)

        # act
        actor = lambda: ssm.add_content_to_loc(inv_state=state, content=new_content)

        # assert
        self.assertRaises(NoRoomAtLocationException, actor)

    def test__mutate_state__add_content_diff_ru__will_fit(self):
        #arrange
        qty=20
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, qty)]),
                                      contents=frozenset([content_factory(resource=skus.sku_a, qty=qty/2, uom=uoms.each)]),)
        new_content = content_factory(resource=skus.sku_b, qty=qty/2, uom=uoms.each)

        # act
        new = ssm.add_content_to_loc(inv_state=state, content=new_content)

        # assert
        self.assertEqual(len(new.containers), len(state.containers) + 1)
        self.assertEqual(new.qty_resource_uom(new_content.resourceUoM), state.qty_resource_uom(new_content.resourceUoM) + new_content.qty)

    def test__mutate_state__add_content_diff_ru__will_not_fit(self):
        #arrange
        qty=20
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, qty)]),
                                      contents=frozenset([content_factory(resource=skus.sku_a, qty=qty/2, uom=uoms.each)]))
        new_content = content_factory(resource=skus.sku_b, qty=qty, uom=uoms.each)

        # act
        actor = lambda: ssm.add_content_to_loc(inv_state=state, content=new_content)

        # assert
        self.assertRaises(NoRoomAtLocationException, actor)

    def test__FIFO__not_extractable(self):
        # arrange
        capacity = 3
        cont_a = content_factory(resource=skus.sku_a, qty=1, uom=uoms.each)
        cont_b = content_factory(resource=skus.sku_a, qty=1, uom=uoms.each)
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, capacity)]),
                                      contents=frozenset(
                                          [cont_a, cont_b]),
                                      location_channel_type=ChannelType.CONTAINER_FIFO_QUEUE
        )

        # act
        actor = lambda: ssm.remove_content_from_location(inv_state=state, content=cont_b)

        # assert
        self.assertRaises(ContentNotInExtractablePositionException, actor)



