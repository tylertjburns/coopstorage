import unittest
from coopstorage.my_dataclasses import LocInvState, Location, Content, ResourceUoM, UoMCapacity, content_factory, loc_inv_state_factory, ContainerState
import coopstorage as ssm
import tests.sku_manifest as skus
import coopstorage.uom_manifest as uoms
from coopstorage.eventDefinition import StorageException, StorageEventType
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

    def test__create_state__with_des(self):
        # arrange
        test_loc = Location(id='Test', uom_capacities=frozenset([x for x in uoms.manifest]))

        # act
        state = LocInvState(
            location=test_loc
        )

        # assert
        self.assertEqual(state.location,test_loc)

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
        container = ContainerState(lpn="dummy", uom=uoms.box, contents=frozenset([content]))
        state = LocInvState(
            location=test_loc,
            containers=tuple([container])
        )

        # assert
        self.assertEqual(state.location,test_loc)
        self.assertEqual(len(state.containers), 1)
        self.assertEqual(state.QtyResourceUoMs[ru], qty)

    def test__mutate_state__add_content_same_ru__will_fit(self):
        #arrange
        qty=20
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, qty)]),
                                      location_channel_type=ChannelType.MERGED_CONTENT)
        new_content = content_factory(resource=skus.sku_a, qty=qty/2, uom=uoms.each)

        # act
        new = ssm.add_content_to_location(inv_state=state, content=new_content)

        # assert
        self.assertEqual(new.QtyResourceUoMs[new_content.resourceUoM], state.QtyResourceUoMs.get(new_content.resourceUoM, 0) + new_content.qty)

    def test__mutate_state__add_content_same_ru__will_not_fit(self):
        #arrange
        qty=20
        state = loc_inv_state_factory(location_channel_type=ChannelType.MERGED_CONTENT,
                                      loc_uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=qty)]))
        new_content = content_factory(resource=skus.sku_a, qty=qty, uom=uoms.each)

        # act
        actor = lambda: ssm.add_content_to_location(inv_state=state, content=new_content)

        # assert
        try:
            actor()
        except StorageException as e:
            self.assertEquals(e.user_args.event_type, StorageEventType.EXCEPTION_QTY_OF_UOM_DOESNT_FIT_AT_DESTINATION)


    def test__mutate_state__add_content_diff_ru__will_fit(self):
        #arrange
        qty=20
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, qty)]),
                                      location_channel_type=ChannelType.MERGED_CONTENT)
        new_content = content_factory(resource=skus.sku_b, qty=qty/2, uom=uoms.each)

        # act
        new = ssm.add_content_to_location(inv_state=state, content=new_content)

        # assert
        self.assertEqual(new.QtyResourceUoMs[new_content.resourceUoM], state.QtyResourceUoMs.get(new_content.resourceUoM, 0) + new_content.qty)

    def test__mutate_state__add_content_diff_ru__will_not_fit(self):
        #arrange
        qty=20
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, qty)]),
                                      location_channel_type=ChannelType.MERGED_CONTENT)
        content1 = content_factory(resource=skus.sku_a, qty=qty/2, uom=uoms.each)
        state = ssm.add_content_to_location(state, content1)

        new_content = content_factory(resource=skus.sku_b, qty=qty, uom=uoms.each)

        # act
        actor = lambda: ssm.add_content_to_location(inv_state=state, content=new_content)

        # assert
        try:
            actor()
        except StorageException as e:
            self.assertEquals(e.user_args.event_type, StorageEventType.EXCEPTION_QTY_OF_UOM_DOESNT_FIT_AT_DESTINATION)

    def test__FIFO__not_extractable(self):
        # arrange
        capacity = 3
        container1 = ContainerState(lpn="dummy1",
                                   uom=uoms.box)
        container2 = ContainerState(lpn="dummy2",
                                    uom=uoms.box)
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, capacity)]),
                                      containers=tuple([container1, container2]),
                                      location_channel_type=ChannelType.FIFO_QUEUE)

        # act
        actor = lambda: ssm.remove_container_from_location(inv_state=state, container=container2)

        # assert
        try:
            actor()
        except StorageException as e:
            self.assertEquals(e.user_args.event_type, StorageEventType.EXCEPTION_CONTAINER_NOT_IN_EXTRACTABLE_POSITION)

    def test__FIFO__extractable(self):
        # arrange
        capacity = 3
        container1 = ContainerState(lpn="dummy1",
                                   uom=uoms.box)
        container2 = ContainerState(lpn="dummy2",
                                    uom=uoms.box)
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, capacity)]),
                                      containers=tuple([container1, container2]),
                                      location_channel_type=ChannelType.FIFO_QUEUE)

        # act
        actor = lambda: ssm.remove_container_from_location(inv_state=state, container=container1)

        # assert
        try:
            actor()
        except StorageException as e:
            self.fail(f"Should not have failed to remove this container")


    def test__LIFO__not_extractable(self):
        # arrange
        capacity = 3
        container1 = ContainerState(lpn="dummy1",
                                   uom=uoms.box)
        container2 = ContainerState(lpn="dummy2",
                                    uom=uoms.box)
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, capacity)]),
                                      containers=tuple([container1, container2]),
                                      location_channel_type=ChannelType.LIFO_QUEUE)

        # act
        actor = lambda: ssm.remove_container_from_location(inv_state=state, container=container1)

        # assert
        try:
            actor()
        except StorageException as e:
            self.assertEquals(e.user_args.event_type, StorageEventType.EXCEPTION_CONTAINER_NOT_IN_EXTRACTABLE_POSITION)

    def test__LIFO__extractable(self):
        # arrange
        capacity = 3
        container1 = ContainerState(lpn="dummy1",
                                   uom=uoms.box)
        container2 = ContainerState(lpn="dummy2",
                                    uom=uoms.box)
        state = loc_inv_state_factory(loc_uom_capacities=frozenset([UoMCapacity(uoms.each, capacity)]),
                                      containers=tuple([container1, container2]),
                                      location_channel_type=ChannelType.LIFO_QUEUE)

        # act
        actor = lambda: ssm.remove_container_from_location(inv_state=state, container=container2)

        # assert
        try:
            actor()
        except StorageException as e:
            self.fail(f"Should not have failed to remove this container")

