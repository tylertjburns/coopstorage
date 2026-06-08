import unittest
from unittest.mock import MagicMock

from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from coopstorage.storage.api.routers.v1.snapshot_router import snapshot_router_factory
from coopstorage.storage.loc_load.reservation_provider import ReservationCheckFailedError


def _make_endpoint(reservation_side_effect=None):
    storage = MagicMock()
    storage.get_locs.return_value = {}
    storage.get_containers.return_value = {}
    storage._data_store.TransferRequestsData.get.return_value = {}
    if reservation_side_effect:
        storage.get_reserved_container_ids.side_effect = reservation_side_effect
    else:
        storage.get_reserved_container_ids.return_value = []
        storage.get_reserved_location_ids.return_value = []
    router = snapshot_router_factory(storage)
    return next(r.endpoint for r in router.routes if isinstance(r, APIRoute))


class TestSnapshotRouter503(unittest.TestCase):

    def test_returns_503_with_retry_after_when_reservation_check_fails(self):
        exc = ReservationCheckFailedError("rate limited", retry_after=7.0)
        result = _make_endpoint(reservation_side_effect=exc)()
        self.assertIsInstance(result, JSONResponse)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.headers["retry-after"], "7")

    def test_returns_503_with_default_retry_after_when_none_provided(self):
        exc = ReservationCheckFailedError("auth error", retry_after=None)
        result = _make_endpoint(reservation_side_effect=exc)()
        self.assertIsInstance(result, JSONResponse)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.headers["retry-after"], "5")

    def test_returns_dict_on_success(self):
        result = _make_endpoint()()
        self.assertIsInstance(result, dict)
        self.assertIn("locations", result)


if __name__ == '__main__':
    unittest.main()
