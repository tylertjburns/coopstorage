import os
import tempfile
import unittest

import coopstorage.storage.loc_load.channel_processors as cps
import coopstorage.storage.loc_load.dcs as dcs
from coopstorage.storage.layout_manager import sqlite_layout_manager
from coopstorage.storage.loc_load.location import Location


def _manager(tmp_path):
    """LayoutManager backed by the given SQLite file path."""
    return sqlite_layout_manager(url=f'sqlite:///{tmp_path}')


class TestLayoutManager(unittest.TestCase):

    def setUp(self):
        fd, self._db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.manager = _manager(self._db_path)
        from coopstorage.storage.loc_load.data.sqlite import db as sqlite_db
        self._engine = sqlite_db.get_engine()

    def tearDown(self):
        self._engine.dispose()
        try:
            os.unlink(self._db_path)
        except FileNotFoundError:
            pass

    def test_create_layout_returns_record_with_name(self):
        layout = self.manager.create_layout('warehouse-a', description='test')
        self.assertEqual(layout.name, 'warehouse-a')
        self.assertEqual(layout.description, 'test')
        self.assertIsNotNone(layout.id)

    def test_get_layout_round_trip(self):
        created = self.manager.create_layout('my-layout')
        fetched = self.manager.get_layout(str(created.id))
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, 'my-layout')

    def test_list_layouts_returns_all_created(self):
        self.manager.create_layout('alpha')
        self.manager.create_layout('beta')
        names = {l.name for l in self.manager.list_layouts()}
        self.assertIn('alpha', names)
        self.assertIn('beta', names)

    def test_get_storage_empty_for_new_layout(self):
        layout = self.manager.create_layout('empty')
        storage = self.manager.get_storage(str(layout.id))
        self.assertEqual(len(storage.get_locs()), 0)

    def test_get_storage_is_cached(self):
        layout = self.manager.create_layout('cached')
        s1 = self.manager.get_storage(str(layout.id))
        s2 = self.manager.get_storage(str(layout.id))
        self.assertIs(s1, s2)

    def test_register_locations_persisted_to_sql(self):
        layout = self.manager.create_layout('with-locs')
        storage = self.manager.get_storage(str(layout.id))

        loc = Location(
            id='Z1-a0-b0-s0',
            location_meta=dcs.LocationMeta(
                dims=(1000, 1000, 1000),
                channel_processor=cps.OMNIChannelProcessor(),
                capacity=1,
            ),
            coords=(0.0, 0.0, 0.0),
        )
        storage.register_locs(locs=[loc])

        # Evict cache and reload from DB to verify persistence
        self.manager.evict(str(layout.id))
        fresh_storage = self.manager.get_storage(str(layout.id))
        self.assertIn('Z1-a0-b0-s0', fresh_storage.get_locs())

    def test_delete_layout_removes_record(self):
        layout = self.manager.create_layout('to-delete')
        self.manager.delete_layout(str(layout.id))
        self.assertIsNone(self.manager.get_layout(str(layout.id)))

    def test_get_unknown_layout_returns_none(self):
        self.assertIsNone(self.manager.get_layout('00000000-0000-0000-0000-000000000000'))


if __name__ == '__main__':
    unittest.main()
