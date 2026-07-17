import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from coopstorage.storage.api.api_factory import storage_api_factory
from coopstorage.storage.layout_manager import sqlite_layout_manager

_LOC_PAYLOAD = {
    'id': 'Z1-a0-b0-s0',
    'coords': {'x': 0.0, 'y': 0.0, 'z': 0.0},
    'meta': {
        'dims': {'x': 1000.0, 'y': 1000.0, 'z': 1000.0},
        'channel_processor_type': 'OMNIChannelProcessor',
        'capacity': 1,
    },
    'tree_labels': {'zone': 'Z1', 'aisle': 0, 'bay': 0, 'shelf': 0},
}


def _client(tmp_path):
    manager = sqlite_layout_manager(url=f'sqlite:///{tmp_path}')
    app = storage_api_factory(layout_manager=manager)
    return TestClient(app, raise_server_exceptions=True)


class TestV2LayoutRouter(unittest.TestCase):

    def setUp(self):
        fd, self._db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.client = _client(self._db_path)
        from coopstorage.storage.loc_load.data.sqlite import db as sqlite_db
        self._engine = sqlite_db.get_engine()

    def tearDown(self):
        self._engine.dispose()
        try:
            os.unlink(self._db_path)
        except FileNotFoundError:
            pass

    # ── Layout CRUD ───────────────────────────────────────────────────────────

    def test_create_layout_returns_201(self):
        resp = self.client.post('/v2/layouts', json={'name': 'test'})
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body['name'], 'test')
        self.assertIn('id', body)

    def test_list_layouts_returns_all(self):
        self.client.post('/v2/layouts', json={'name': 'alpha'})
        self.client.post('/v2/layouts', json={'name': 'beta'})
        resp = self.client.get('/v2/layouts')
        self.assertEqual(resp.status_code, 200)
        names = {l['name'] for l in resp.json()}
        self.assertIn('alpha', names)
        self.assertIn('beta', names)

    def test_get_layout_returns_record(self):
        layout_id = self.client.post('/v2/layouts', json={'name': 'get-test'}).json()['id']
        resp = self.client.get(f'/v2/layouts/{layout_id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['name'], 'get-test')

    def test_get_unknown_layout_returns_404(self):
        resp = self.client.get('/v2/layouts/00000000-0000-0000-0000-000000000000')
        self.assertEqual(resp.status_code, 404)

    # ── Location CRUD ─────────────────────────────────────────────────────────

    def _create_layout(self, name='test-layout'):
        return self.client.post('/v2/layouts', json={'name': name}).json()['id']

    def test_put_locations_happy_path(self):
        layout_id = self._create_layout()
        resp = self.client.put(
            f'/v2/layouts/{layout_id}/locations',
            json={'locations': [_LOC_PAYLOAD]},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Z1-a0-b0-s0', resp.json()['registered'])

    def test_get_locations_returns_placed_locs(self):
        layout_id = self._create_layout()
        self.client.put(
            f'/v2/layouts/{layout_id}/locations',
            json={'locations': [_LOC_PAYLOAD]},
        )
        locs = self.client.get(f'/v2/layouts/{layout_id}/locations').json()
        self.assertIn('Z1-a0-b0-s0', locs)

    def test_get_locations_includes_snapshot_fields(self):
        """Response must use snapshot format (slots, containers) not raw Location dict."""
        layout_id = self._create_layout()
        self.client.put(
            f'/v2/layouts/{layout_id}/locations',
            json={'locations': [_LOC_PAYLOAD]},
        )
        loc = self.client.get(f'/v2/layouts/{layout_id}/locations').json()['Z1-a0-b0-s0']
        self.assertIn('slots', loc)
        self.assertIn('containers', loc)

    def test_put_duplicate_location_returns_409(self):
        layout_id = self._create_layout()
        payload = {'locations': [_LOC_PAYLOAD]}
        self.client.put(f'/v2/layouts/{layout_id}/locations', json=payload)
        resp = self.client.put(f'/v2/layouts/{layout_id}/locations', json=payload)
        self.assertEqual(resp.status_code, 409)
        self.assertIn('already exist', resp.json()['detail'])

    def test_delete_location_removes_it(self):
        layout_id = self._create_layout()
        self.client.put(
            f'/v2/layouts/{layout_id}/locations',
            json={'locations': [_LOC_PAYLOAD]},
        )
        resp = self.client.delete(f'/v2/layouts/{layout_id}/locations/Z1-a0-b0-s0')
        self.assertIn(resp.status_code, (200, 204))

        locs = self.client.get(f'/v2/layouts/{layout_id}/locations').json()
        self.assertNotIn('Z1-a0-b0-s0', locs)

    def test_delete_unknown_location_returns_404(self):
        layout_id = self._create_layout()
        resp = self.client.delete(f'/v2/layouts/{layout_id}/locations/nonexistent')
        self.assertEqual(resp.status_code, 404)

    def test_put_locations_unknown_layout_returns_404(self):
        resp = self.client.put(
            '/v2/layouts/00000000-0000-0000-0000-000000000000/locations',
            json={'locations': [_LOC_PAYLOAD]},
        )
        self.assertEqual(resp.status_code, 404)

    # ── LocationDataStore.remove(ids=…) unit path ─────────────────────────────

    def test_remove_by_ids_via_delete_endpoint(self):
        """DELETE endpoint calls LocationDataStore.remove(ids=[loc_id]) — verify it works."""
        layout_id = self._create_layout()
        self.client.put(
            f'/v2/layouts/{layout_id}/locations',
            json={'locations': [_LOC_PAYLOAD]},
        )
        # Two-step: confirm present, then delete
        self.assertIn('Z1-a0-b0-s0',
                      self.client.get(f'/v2/layouts/{layout_id}/locations').json())
        self.client.delete(f'/v2/layouts/{layout_id}/locations/Z1-a0-b0-s0')
        self.assertNotIn('Z1-a0-b0-s0',
                         self.client.get(f'/v2/layouts/{layout_id}/locations').json())


if __name__ == '__main__':
    unittest.main()
