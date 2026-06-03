"""
Tests for reservation_provider.py

Covers:
- PassthroughReservationProvider.is_reserved / get_reserved_ids
- ApiKeyReservationProvider.is_reserved / get_reserved_ids  (_get + POST /check)
- JwtExchangeReservationProvider.is_reserved / get_reserved_ids (_get with token/retry)
"""
import time
import unittest
from unittest.mock import MagicMock, patch

from coopstorage.storage.loc_load.reservation_provider import (
    PassthroughReservationProvider,
    ApiKeyReservationProvider,
    JwtExchangeReservationProvider,
    ReservationCheckFailedError,
)


# ── PassthroughReservationProvider ────────────────────────────────────────────

class TestPassthroughReservationProvider(unittest.TestCase):

    def setUp(self):
        self.provider = PassthroughReservationProvider()

    def test_is_reserved_always_false(self):
        self.assertFalse(self.provider.is_reserved('any-resource'))

    def test_is_reserved_after_reserve_still_false(self):
        self.provider.reserve('r1', 'requester')
        self.assertFalse(self.provider.is_reserved('r1'))

    def test_get_reserved_ids_always_empty(self):
        self.assertEqual(self.provider.get_reserved_ids(['a', 'b', 'c']), set())

    def test_get_reserved_ids_empty_input(self):
        self.assertEqual(self.provider.get_reserved_ids([]), set())


# ── ApiKeyReservationProvider ─────────────────────────────────────────────────

class TestApiKeyReservationProviderCheckMethods(unittest.TestCase):

    def setUp(self):
        self.provider = ApiKeyReservationProvider(
            base_url='http://test-host',
            api_key='test-api-key',
        )
        self._expected_headers = {'X-Api-Key': 'test-api-key'}
        self.mock_session = MagicMock()
        self.provider._session = self.mock_session

    def _mock_get_response(self, payload, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = payload
        resp.raise_for_status = MagicMock()
        return resp

    def _mock_post_response(self, payload, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = payload
        resp.raise_for_status = MagicMock()
        return resp

    def test_is_reserved_returns_true_when_api_says_reserved(self):
        self.mock_session.get.return_value = self._mock_get_response(
            {'resource': 'r1', 'isReserved': True, 'holder': 'someone'}
        )
        self.assertTrue(self.provider.is_reserved('r1'))
        self.mock_session.get.assert_called_once_with(
            'http://test-host/api/v1/Reservation/check/r1',
            headers=self._expected_headers,
            timeout=10.0,
        )

    def test_is_reserved_returns_false_when_api_says_not_reserved(self):
        self.mock_session.get.return_value = self._mock_get_response(
            {'resource': 'r1', 'isReserved': False, 'holder': None}
        )
        self.assertFalse(self.provider.is_reserved('r1'))

    def test_get_reserved_ids_returns_only_reserved_resources(self):
        self.mock_session.post.return_value = self._mock_post_response([
            {'resource': 'r1', 'isReserved': True,  'holder': 'x'},
            {'resource': 'r2', 'isReserved': False, 'holder': None},
            {'resource': 'r3', 'isReserved': True,  'holder': 'y'},
        ])
        result = self.provider.get_reserved_ids(['r1', 'r2', 'r3'])
        self.assertEqual(result, {'r1', 'r3'})
        self.mock_session.post.assert_called_once_with(
            'http://test-host/api/v1/Reservation/check',
            json={'resources': ['r1', 'r2', 'r3']},
            headers=self._expected_headers,
            timeout=10.0,
        )

    def test_get_reserved_ids_empty_when_none_reserved(self):
        self.mock_session.post.return_value = self._mock_post_response([
            {'resource': 'r1', 'isReserved': False},
        ])
        self.assertEqual(self.provider.get_reserved_ids(['r1']), set())

    def test_get_reserved_ids_empty_input_returns_empty_set(self):
        self.mock_session.post.return_value = self._mock_post_response([])
        self.assertEqual(self.provider.get_reserved_ids([]), set())

    def _mock_429_response(self, retry_after_secs):
        resp = MagicMock()
        resp.status_code = 429
        resp.headers = {'Retry-After': str(retry_after_secs)}
        resp.json.return_value = {}
        resp.reason = 'Too Many Requests'
        return resp

    def test_is_reserved_propagates_retry_after_on_rate_limit(self):
        self.mock_session.get.return_value = self._mock_429_response(15.0)
        with self.assertRaises(ReservationCheckFailedError) as ctx:
            self.provider.is_reserved('r1')
        self.assertEqual(ctx.exception.retry_after, 15.0)

    def test_get_reserved_ids_propagates_retry_after_on_rate_limit(self):
        self.mock_session.post.return_value = self._mock_429_response(20.0)
        with self.assertRaises(ReservationCheckFailedError) as ctx:
            self.provider.get_reserved_ids(['r1', 'r2'])
        self.assertEqual(ctx.exception.retry_after, 20.0)


# ── JwtExchangeReservationProvider ────────────────────────────────────────────

class TestJwtExchangeReservationProviderCheckMethods(unittest.TestCase):

    def setUp(self):
        self.provider = JwtExchangeReservationProvider(
            base_url='http://jwt-host',
            api_key='jwt-api-key',
        )
        # Pre-set a valid token to bypass the exchange call in these tests
        self.provider._token = 'test-jwt-token'
        self.provider._token_expires_at = time.monotonic() + 3600
        self.mock_session = MagicMock()
        self.provider._session = self.mock_session

    def _mock_get_response(self, payload, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = payload
        resp.raise_for_status = MagicMock()
        return resp

    def _mock_post_response(self, payload, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = payload
        resp.raise_for_status = MagicMock()
        return resp

    def test_is_reserved_returns_true_when_api_says_reserved(self):
        self.mock_session.get.return_value = self._mock_get_response(
            {'resource': 'r1', 'isReserved': True, 'holder': 'holder-x'}
        )
        self.assertTrue(self.provider.is_reserved('r1'))
        self.mock_session.get.assert_called_once_with(
            'http://jwt-host/api/v1/Reservation/check/r1',
            headers={'Authorization': 'Bearer test-jwt-token'},
            timeout=10.0,
        )

    def test_is_reserved_returns_false_when_api_says_not_reserved(self):
        self.mock_session.get.return_value = self._mock_get_response(
            {'resource': 'r1', 'isReserved': False, 'holder': None}
        )
        self.assertFalse(self.provider.is_reserved('r1'))

    def test_is_reserved_retries_once_on_401(self):
        """On a 401 the token is invalidated and the request retried exactly once."""
        unauthorized = self._mock_get_response({}, status_code=401)
        ok = self._mock_get_response({'resource': 'r1', 'isReserved': True}, status_code=200)
        self.mock_session.get.side_effect = [unauthorized, ok]

        with patch.object(self.provider, '_exchange_token') as mock_exchange:
            result = self.provider.is_reserved('r1')

        self.assertTrue(result)
        self.assertEqual(self.mock_session.get.call_count, 2)
        mock_exchange.assert_called_once()

    def test_get_reserved_ids_returns_reserved_subset(self):
        self.mock_session.post.return_value = self._mock_post_response([
            {'resource': 'r1', 'isReserved': True},
            {'resource': 'r2', 'isReserved': False},
        ])
        result = self.provider.get_reserved_ids(['r1', 'r2'])
        self.assertEqual(result, {'r1'})

    def test_get_reserved_ids_empty_when_none_reserved(self):
        self.mock_session.post.return_value = self._mock_post_response([
            {'resource': 'r1', 'isReserved': False},
        ])
        self.assertEqual(self.provider.get_reserved_ids(['r1']), set())


if __name__ == '__main__':
    unittest.main()
