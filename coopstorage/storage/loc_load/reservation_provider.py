import threading
import time
from typing import Iterable, Optional, Protocol
import logging
import requests

logger = logging.getLogger(__name__)


class RateLimitedError(Exception):
    """Raised when a 429 retryAfter exceeds max_retry_wait; carries retry_after for callers."""
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limited; retryAfter={retry_after:.1f}s exceeds max_retry_wait")


class ReservationFailedError(Exception):
    """Raised by reserve/unreserve when the operation cannot complete due to rate limiting."""
    def __init__(self, message: str):
        super().__init__(message)


class ReservationCheckFailedError(Exception):
    """Raised by is_reserved/get_reserved_ids when the check cannot complete due to rate limiting."""
    def __init__(self, message: str):
        super().__init__(message)


class ReservationProvider(Protocol):
    def reserve(self, resource: str, requester: str, resource_type: str = None) -> Optional[str]: ...
    def unreserve(self, resource: str, requester: str, token: str) -> bool: ...
    def is_reserved(self, resource: str) -> bool: ...
    def get_reserved_ids(self, resource_ids: Iterable[str]) -> set: ...


class PassthroughReservationProvider:
    """Always grants reservations. Used as the default when no external provider is configured."""

    def reserve(self, resource: str, requester: str, resource_type: str = None) -> Optional[str]:
        return resource

    def unreserve(self, resource: str, requester: str, token: str) -> bool:
        return True

    def is_reserved(self, resource: str) -> bool:
        return False

    def get_reserved_ids(self, resource_ids: Iterable[str]) -> set:
        return set()


class _HttpReservationBase:
    """Shared HTTP transport, retry, and logging logic for reservation providers.

    Subclasses implement _make_headers() to supply authentication credentials,
    and may override _on_auth_failure() to invalidate cached tokens on 401.
    """

    def __init__(self, base_url: str, max_retry_wait: float = 10.0):
        self._base_url = base_url.rstrip('/')
        self._max_retry_wait = max_retry_wait

    def _make_headers(self) -> dict:
        raise NotImplementedError

    def _on_auth_failure(self):
        """Called when a 401 Unauthorized response is received. Override to invalidate cached credentials."""
        pass

    def _post(self, path: str, body, *, _re_auth: bool = True, attempts: int = 3) -> list:
        try:
            headers = self._make_headers()
        except requests.exceptions.ConnectionError:
            logger.warning(f"Auth unavailable for POST {path} — service unreachable")
            return []

        logger.debug(f"POST {path}")
        t0 = time.monotonic()
        try:
            resp = requests.post(f"{self._base_url}{path}", json=body, headers=headers)
        except requests.exceptions.ConnectionError:
            elapsed = time.monotonic() - t0
            logger.warning(f"POST {path} — connection error after {elapsed:.3f}s")
            return []
        elapsed = time.monotonic() - t0
        logger.debug(f"POST {path} → HTTP {resp.status_code} {resp.reason} in {elapsed:.3f}s")

        if resp.status_code == 401 and _re_auth:
            logger.warning(f"401 Unauthorized on POST {path} — refreshing auth and retrying")
            self._on_auth_failure()
            return self._post(path, body, _re_auth=False, attempts=attempts)

        if resp.status_code == 429:
            body_data = {}
            try:
                body_data = resp.json()
            except Exception:
                pass
            retry_after = float(body_data.get('retryAfter') or resp.headers.get('Retry-After', 1))
            if retry_after > self._max_retry_wait:
                logger.error(
                    f"429 Too Many Requests on POST {path} — retryAfter={retry_after:.1f}s "
                    f"exceeds max_retry_wait={self._max_retry_wait:.1f}s; failing fast"
                )
                raise RateLimitedError(retry_after)
            retry_at = time.strftime('%H:%M:%S', time.localtime(time.time() + retry_after))
            logger.warning(
                f"429 Too Many Requests on POST {path} — retryAfter={retry_after:.1f}s; retrying at {retry_at}"
            )
            time.sleep(retry_after)
            return self._post(path, body, _re_auth=_re_auth, attempts=attempts)

        if resp.status_code >= 500 and attempts > 0:
            logger.warning(
                f"HTTP {resp.status_code} {resp.reason} on POST {path} — retrying ({attempts} attempts left)"
            )
            time.sleep(1)
            return self._post(path, body, _re_auth=_re_auth, attempts=attempts - 1)

        if resp.status_code >= 400:
            logger.error(f"POST {path} failed: HTTP {resp.status_code} {resp.reason}: {resp.text}")
            raise requests.HTTPError(f"POST {path} failed: {resp.status_code}")

        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str, *, _re_auth: bool = True) -> dict:
        try:
            headers = self._make_headers()
        except requests.exceptions.ConnectionError:
            logger.warning(f"Auth unavailable for GET {path} — service unreachable")
            return {}

        logger.debug(f"GET {path}")
        t0 = time.monotonic()
        try:
            resp = requests.get(f"{self._base_url}{path}", headers=headers)
        except requests.exceptions.ConnectionError:
            elapsed = time.monotonic() - t0
            logger.warning(f"GET {path} — connection error after {elapsed:.3f}s")
            return {}
        elapsed = time.monotonic() - t0
        logger.debug(f"GET {path} → HTTP {resp.status_code} {resp.reason} in {elapsed:.3f}s")

        if resp.status_code == 401 and _re_auth:
            logger.warning(f"401 Unauthorized on GET {path} — refreshing auth and retrying")
            self._on_auth_failure()
            return self._get(path, _re_auth=False)

        if resp.status_code == 429:
            body_data = {}
            try:
                body_data = resp.json()
            except Exception:
                pass
            retry_after = float(body_data.get('retryAfter') or resp.headers.get('Retry-After', 1))
            if retry_after > self._max_retry_wait:
                logger.error(
                    f"429 Too Many Requests on GET {path} — retryAfter={retry_after:.1f}s "
                    f"exceeds max_retry_wait={self._max_retry_wait:.1f}s; failing fast"
                )
                raise RateLimitedError(retry_after)
            retry_at = time.strftime('%H:%M:%S', time.localtime(time.time() + retry_after))
            logger.warning(
                f"429 Too Many Requests on GET {path} — retryAfter={retry_after:.1f}s; retrying at {retry_at}"
            )
            time.sleep(retry_after)
            return self._get(path, _re_auth=_re_auth)

        resp.raise_for_status()
        return resp.json()

    def reserve(self, resource: str, requester: str, resource_type: str = None) -> Optional[str]:
        try:
            results = self._post('/api/v1/Reservation/reserve', [
                {'requester': requester, 'resource': resource, 'resourceType': resource_type or 'storage'}
            ])
        except RateLimitedError as exc:
            raise ReservationFailedError(
                f"reserve rate-limited (retryAfter={exc.retry_after:.1f}s): resource={resource} requester={requester}"
            ) from exc
        if results and results[0].get('status') == 'SUCCESS':
            token = results[0].get('releaseToken')
            if token is None:
                logger.error(
                    f"Reserve succeeded but releaseToken missing: resource={resource} response={results[0]}"
                )
                return None
            logger.debug(f"Reserve OK: resource={resource} token={token}")
            return token
        explanation = results[0].get('explanation') if results else 'empty response (service unreachable?)'
        logger.error(
            f"Reserve FAILED: resource={resource} requester={requester} "
            f"explanation={explanation} response={results}"
        )
        return None

    def unreserve(self, resource: str, requester: str, token: str) -> bool:
        try:
            results = self._post('/api/v1/Reservation/unreserve', [
                {'requester': requester, 'resource': resource, 'releaseToken': token}
            ])
        except RateLimitedError as exc:
            raise ReservationFailedError(
                f"unreserve rate-limited (retryAfter={exc.retry_after:.1f}s): resource={resource} requester={requester}"
            ) from exc
        success = bool(results and results[0].get('status') == 'SUCCESS')
        if not success:
            reason = results[0].get('explanation') if results else 'no response'
            logger.error(
                f"Unreserve FAILED: resource={resource} requester={requester} "
                f"token={token} reason={reason} response={results}"
            )
        return success

    def is_reserved(self, resource: str) -> bool:
        t0 = time.monotonic()
        logger.debug(f"is_reserved: checking resource={resource}")
        try:
            result = self._get(f'/api/v1/Reservation/check/{resource}')
        except RateLimitedError as exc:
            raise ReservationCheckFailedError(
                f"is_reserved rate-limited (retryAfter={exc.retry_after:.1f}s): resource={resource}"
            ) from exc
        elapsed = time.monotonic() - t0
        is_res = result.get('isReserved', False)
        logger.debug(f"is_reserved: resource={resource} → {is_res} ({elapsed:.3f}s)")
        return is_res

    def get_reserved_ids(self, resource_ids: Iterable[str]) -> set:
        ids = list(resource_ids)
        if not ids:
            return set()
        t0 = time.monotonic()
        logger.debug(f"get_reserved_ids: checking {len(ids)} IDs")
        try:
            results = self._post('/api/v1/Reservation/check', {'resources': ids})
        except RateLimitedError as exc:
            raise ReservationCheckFailedError(
                f"get_reserved_ids rate-limited (retryAfter={exc.retry_after:.1f}s): {len(ids)} IDs"
            ) from exc
        elapsed = time.monotonic() - t0
        reserved = {r['resource'] for r in results if r.get('isReserved')}
        logger.debug(f"get_reserved_ids: {len(ids)} IDs → {len(reserved)} reserved in {elapsed:.3f}s")
        return reserved


class ApiKeyReservationProvider(_HttpReservationBase):
    """Authenticates via X-Api-Key header on every request."""

    def __init__(self, base_url: str, api_key: str, max_retry_wait: float = 10.0):
        super().__init__(base_url, max_retry_wait=max_retry_wait)
        self._api_key = api_key

    def _make_headers(self) -> dict:
        return {'X-Api-Key': self._api_key}


class JwtExchangeReservationProvider(_HttpReservationBase):
    """Exchanges an API key for a short-lived JWT Bearer token via POST /auth/token.

    The token is cached and refreshed proactively before expiry using the expiresIn
    value returned by the server. On a 401 response the token is invalidated and the
    request is retried once to handle clock skew. Thread-safe.
    """

    _EXPIRY_BUFFER_SECONDS = 30

    def __init__(self, base_url: str, api_key: str, max_retry_wait: float = 10.0):
        super().__init__(base_url, max_retry_wait=max_retry_wait)
        self._api_key = api_key
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._token_lock = threading.Lock()

    def _exchange_token(self):
        try:
            resp = requests.post(
                f"{self._base_url}/auth/token",
                headers={'X-Api-Key': self._api_key},
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            logger.warning(
                f"Reservation service unreachable at {self._base_url}/auth/token — will retry on next request."
            )
            raise
        data = resp.json()
        self._token = data['accessToken']
        expires_in = data['expiresIn']
        self._token_expires_at = time.monotonic() + expires_in - self._EXPIRY_BUFFER_SECONDS

    def _get_token(self) -> str:
        with self._token_lock:
            if self._token is None or time.monotonic() >= self._token_expires_at:
                self._exchange_token()
            return self._token

    def _invalidate_token(self):
        with self._token_lock:
            self._token = None

    def _make_headers(self) -> dict:
        return {'Authorization': f'Bearer {self._get_token()}'}

    def _on_auth_failure(self):
        self._invalidate_token()
