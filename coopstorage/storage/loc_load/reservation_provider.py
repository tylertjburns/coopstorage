from typing import Optional, Protocol
import requests


class ReservationProvider(Protocol):
    def reserve(self, resource: str, requester: str) -> Optional[str]: ...
    def unreserve(self, resource: str, requester: str) -> bool: ...


class PassthroughReservationProvider:
    """Always grants reservations. Used as the default when no external provider is configured."""

    def reserve(self, resource: str, requester: str) -> Optional[str]:
        return resource

    def unreserve(self, resource: str, requester: str) -> bool:
        return True


class LockerApiReservationProvider:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip('/')

    def reserve(self, resource: str, requester: str) -> Optional[str]:
        resp = requests.post(
            f"{self._base_url}/api/Reservation/reserve",
            json=[{"requester": requester, "resource": resource}],
        )
        resp.raise_for_status()
        results = resp.json()
        if results and results[0].get("status") == "SUCCESS":
            return resource
        return None

    def unreserve(self, resource: str, requester: str) -> bool:
        resp = requests.post(
            f"{self._base_url}/api/Reservation/unreserve",
            json=[{"requester": requester, "resource": resource}],
        )
        resp.raise_for_status()
        results = resp.json()
        return bool(results and results[0].get("status") == "SUCCESS")
