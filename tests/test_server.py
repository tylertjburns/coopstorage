import os
import unittest
from unittest import mock

from authlib.integrations.starlette_client.apps import StarletteOAuth2App
from fastapi.testclient import TestClient

from coopstorage.storage.api.server import HOME_PATH, create_app

_ENV = {
    'GOOGLE_CLIENT_ID': 'test-client-id',
    'GOOGLE_CLIENT_SECRET': 'test-client-secret',
    'SESSION_SECRET': 'test-session-secret',
    'ALLOWED_EMAILS': 'Owner@Example.com',
    'SESSION_HTTPS_ONLY': 'false',
    'COOPSTORAGE_BUILD_VERSION': 'v-test',
}


def _google_returns(email: str, verified: bool = True):
    token = {'userinfo': {'email': email, 'email_verified': verified}}
    return mock.patch.object(StarletteOAuth2App, 'authorize_access_token', mock.AsyncMock(return_value=token))


class TestServer(unittest.TestCase):

    def setUp(self):
        env = mock.patch.dict(os.environ, _ENV)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('DATABASE_URL', None)
        self.client = TestClient(create_app(), follow_redirects=False)

    def _sign_in(self, email: str, verified: bool = True):
        with _google_returns(email, verified):
            return self.client.get('/auth/callback')

    def test_health_is_public_and_reports_version(self):
        res = self.client.get('/health')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'status': 'ok', 'version': 'v-test'})

    def test_api_request_without_session_is_401(self):
        res = self.client.get('/v1/simulate/status')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 'not_signed_in')

    def test_browser_request_without_session_redirects_to_login(self):
        res = self.client.get(HOME_PATH, headers={'accept': 'text/html'})
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers['location'], '/auth/login')

    def test_allowed_email_signs_in_and_reaches_app(self):
        res = self._sign_in('owner@example.com')
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers['location'], HOME_PATH)
        self.assertEqual(self.client.get(HOME_PATH).status_code, 200)

    def test_other_email_is_refused(self):
        self.assertEqual(self._sign_in('someone@example.com').status_code, 403)
        self.assertEqual(self.client.get('/v1/simulate/status').status_code, 401)

    def test_unverified_email_is_refused(self):
        self.assertEqual(self._sign_in('owner@example.com', verified=False).status_code, 403)

    def test_logout_ends_session(self):
        self._sign_in('owner@example.com')
        self.assertEqual(self.client.post('/auth/logout').status_code, 204)
        self.assertEqual(self.client.get('/v1/simulate/status').status_code, 401)

    def test_missing_config_fails_at_startup(self):
        with mock.patch.dict(os.environ, {'SESSION_SECRET': ''}):
            with self.assertRaises(RuntimeError):
                create_app()


if __name__ == '__main__':
    unittest.main()
