import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from coopstorage.storage.api.routers.v1.snapshot_router import snapshot_router_factory
from coopstorage.storage.loc_load.reservation_provider import ReservationCheckFailedError


def _make_client(reservation_side_effect=None):
    storage = MagicMock()
    storage.get_locs.return_value = {}
    storage.get_containers.return_value = {}
    storage._data_store.TransferRequestsData.get.return_value = {}
    if reservation_side_effect:
        storage.get_reserved_container_ids.side_effect = reservation_side_effect
    else:
        storage.get_reserved_container_ids.return_value = []
        storage.get_reserved_location_ids.return_value = []
    app = FastAPI()
    app.include_router(snapshot_router_factory(storage))
    return TestClient(app)


class TestSnapshotRouter503(unittest.TestCase):

    def test_returns_503_with_retry_after_when_reservation_check_fails(self):
        exc = ReservationCheckFailedError("rate limited", retry_after=7.0)
        resp = _make_client(reservation_side_effect=exc).get("/snapshot")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.headers.get("Retry-After"), "7")
        self.assertIn("detail", resp.json())

    def test_returns_503_with_default_retry_after_when_none_provided(self):
        exc = ReservationCheckFailedError("auth error", retry_after=None)
        resp = _make_client(reservation_side_effect=exc).get("/snapshot")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.headers.get("Retry-After"), "5")

    def test_returns_200_on_success(self):
        resp = _make_client().get("/snapshot")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("locations", resp.json())


if __name__ == '__main__':
    unittest.main()
