from coopstorage.my_dataclasses import ContainerState, UnitOfMeasure, Content, container_factory
import unittest
import coopstorage.uom_manifest as uoms

class Test_Dataclass_Container(unittest.TestCase):
    def test_init_cntnr(self):
        # arrange
        lpn = "name"
        uom = uoms.each

        # act
        cnt = ContainerState(
            lpn=lpn,
            uom=uom
        )

        # assert
        self.assertEqual(cnt.lpn, lpn)
        self.assertEqual(cnt.uom, uom)
        self.assertEqual(cnt.contents, [])

    def test__cntnr_factory__from_cntnr(self):
        # arrange
        lpn = "name"
        uom = uoms.each
        cnt = ContainerState(
            lpn=lpn,
            uom=uom
        )

        # act
        new_cnt = container_factory(cnt)

        # assert
        self.assertEqual(cnt, new_cnt)


    def test__cntnr_factory__from_attrs(self):
        # arrange
        lpn = "name"
        uom = uoms.each

        # act
        new_cnt = container_factory(lpn=lpn, uom=uom)

        # assert
        self.assertEqual(new_cnt.lpn, lpn)
        self.assertEqual(new_cnt.uom, uom)
