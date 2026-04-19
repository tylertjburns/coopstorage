import threading
import time
from typing import Optional, Protocol
import logging
import requests


class ReservationProvider(Protocol):
    def reserve(self, resource: str, requester: str, resource_type: str = None) -> Optional[str]: ...
    def unreserve(self, resource: str, requester: str) -> bool: ...


class PassthroughReservationProvider:
    """Always grants reservations. Used as the default when no external provider is configured."""

    def reserve(self, resource: str, requester: str, resource_type: str = None) -> Optional[str]:
        return resource

    def unreserve(self, resource: str, requester: str) -> bool:
        return True


class ApiKeyReservationProvider:
    """Authenticates via X-Api-Key header on every request."""

    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip('/')
        self._api_key = api_key

    def _headers(self) -> dict:
        return {'X-Api-Key': self._api_key}

    def _post(self, path: str, body) -> list:
        resp = requests.post(f"{self._base_url}{path}", json=body, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def reserve(self, resource: str, requester: str, resource_type: str = None) -> Optional[str]:
        results = self._post('/api/v1/Reservation/reserve', [{'requester': requester, 'resource': resource, 'resourceType': resource_type or "storage" }])
        if results and results[0].get('status') == 'SUCCESS':
            return resource
        return None

    def unreserve(self, resource: str, requester: str) -> bool:
        results = self._post('/api/v1/Reservation/unreserve', [{'requester': requester, 'resource': resource}])
        return bool(results and results[0].get('status') == 'SUCCESS')


class JwtExchangeReservationProvider:
    """Exchanges an API key for a short-lived JWT Bearer token via POST /auth/token.

    The token is cached and refreshed proactively before expiry using the expiresIn
    value returned by the server. On a 401 response the token is invalidated and the
    request is retried once to handle clock skew. Thread-safe.
    """

    _EXPIRY_BUFFER_SECONDS = 30

    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip('/')
        self._api_key = api_key
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._lock = threading.Lock()

    def _exchange_token(self):
        resp = requests.post(
            f"{self._base_url}/auth/token",
            headers={'X-Api-Key': self._api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data['accessToken']
        expires_in = data['expiresIn']
        self._token_expires_at = time.monotonic() + expires_in - self._EXPIRY_BUFFER_SECONDS

    def _get_token(self) -> str:
        with self._lock:
            if self._token is None or time.monotonic() >= self._token_expires_at:
                self._exchange_token()
            return self._token

    def _invalidate_token(self):
        with self._lock:
            self._token = None

    def _post(self, path: str, body, *, _re_auth: bool = True, attempts: int = 3) -> list:
        headers = {'Authorization': f'Bearer {self._get_token()}'}
        logging.debug(f"Sending request to {path}")
        resp = requests.post(f"{self._base_url}{path}", json=body, headers=headers)
        if resp.status_code == 401 and _re_auth:
            logging.warning("Received 401 Unauthorized, refreshing token and retrying...")
            self._invalidate_token()
            return self._post(path, body, _re_auth=False)
        elif resp.status_code == 429:
            logging.warning(f"Received 429 Too Many Requests, retrying after backoff...")
            retry_after = int(resp.headers.get('Retry-After', '1'))
            time.sleep(retry_after)
            return self._post(path, body, _re_auth=_re_auth, attempts=attempts)
        elif resp.status_code >= 500 and attempts > 0:
            logging.warning(f"Received {resp.status_code} Internal Server Error, retrying after backoff...")
            time.sleep(1)  # Backoff before retrying
            return self._post(path, body, _re_auth=_re_auth, attempts=attempts - 1)
        elif resp.status_code >= 400:
            logging.error(f"Request to {path} failed with status {resp.status_code}: {resp.text}")
            raise requests.HTTPError(f"Request to {path} failed with status {resp.status_code}: {resp.text}")   
        resp.raise_for_status()
        return resp.json()

    def reserve(self, resource: str, requester: str, resource_type: str = None) -> Optional[str]:
        results = self._post('/api/v1/Reservation/reserve', [{'requester': requester, 'resource': resource, 'resourceType': resource_type or "storage" }])
        if results and results[0].get('status') == 'SUCCESS':
            return resource
        return None

    def unreserve(self, resource: str, requester: str) -> bool:
        results = self._post('/api/v1/Reservation/unreserve', [{'requester': requester, 'resource': resource}])
        return bool(results and results[0].get('status') == 'SUCCESS')
