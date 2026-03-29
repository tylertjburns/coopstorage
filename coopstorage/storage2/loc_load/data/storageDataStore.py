from cooptools.dataStore.inMemoryDataStore import InMemoryDataStore
from cooptools.dataStore.dataStoreProtocol import DataStoreProtocol
import coopstorage.storage2.loc_load.qualifiers as qs
from typing import Self, List, Iterable, Dict
from coopstorage.storage2.loc_load import dcs
from coopstorage.storage2.loc_load.location import Location
from coopstorage.storage2.loc_load.transferRequest import TransferRequest
from cooptools.protocols import UniqueIdentifier

class ContainerDataStore:
    def __init__(self,
                 data_store: DataStoreProtocol):
        self._data_store = data_store

    def get(self,
            ids: Iterable[UniqueIdentifier]=None,
            qualifier: qs.ContainerQualifier=None) -> Dict[UniqueIdentifier, dcs.Container]:
        ret = self._data_store.get(ids=ids, id_query=qualifier.pattern if qualifier is not None else None)
        if qualifier is not None:
            ret = {k: v for k, v in ret.items() if qualifier.check_if_qualifies(v)}
        return ret

    def clear(self) -> Self:
        self._data_store.clear()
        return self

    def add(self, containers: Iterable[dcs.Container]):
        self._data_store.add(containers)
        return self

    def add_or_update(self, containers: Iterable[dcs.Container]):
        self._data_store.add_or_update(containers)
        return self

    def remove(self, containers: Iterable[dcs.Container]):
        self._data_store.remove(containers)
        return self

class LocationDataStore:
    def __init__(self,
                 data_store: DataStoreProtocol):
        self._data_store = data_store

    def get(self,
            qualifier: qs.LocationQualifier = None,
            ids: Iterable[UniqueIdentifier] = None,
            container_provider: qs.ContainerByIdProvider = None) -> Dict[UniqueIdentifier, Location]:
        if ids is not None:
            return self._data_store.get(ids=ids)

        ret = self._data_store.get(id_query=qualifier.id_pattern if qualifier is not None else None)
        if qualifier is not None:
            ret = {k: v for k, v in ret.items() if qualifier.check_if_qualifies(v, container_provider=container_provider)}
        return ret

    def clear(self) -> Self:
        self._data_store.clear()
        return self

    def add(self, locs: Iterable[Location]):
        self._data_store.add(locs)
        return self

    def update(self, locs: Iterable[Location]):
        self._data_store.update(locs)
        return self

    def remove(self, locs: Iterable[Location]):
        self._data_store.remove(locs)
        return self

class TransferRequestDataStore:
    def __init__(self,
                 data_store: DataStoreProtocol):
        self._data_store = data_store

    def get(self) -> Dict[UniqueIdentifier, TransferRequest]:
        ret = self._data_store.get()
        return ret

    def clear(self) -> Self:
        self._data_store.clear()
        return self

    def add(self, requests: Iterable[TransferRequest]) -> Self:
        self._data_store.add(requests)
        return self

    def remove(self, requests: Iterable[TransferRequest]):
        self._data_store.remove(requests)
        return self


class StorageDataStore:
    def __init__(self,
                 containers_data_store: DataStoreProtocol = None,
                 location_data_store: DataStoreProtocol = None,
                 transfer_request_data_store: DataStoreProtocol = None
                 ):
        self._containers_data_store: ContainerDataStore = ContainerDataStore(data_store=containers_data_store or InMemoryDataStore())
        self._locs_data_store: LocationDataStore = LocationDataStore(
            data_store=location_data_store or InMemoryDataStore())
        self._transfer_requests_data_store: TransferRequestDataStore = TransferRequestDataStore(
            data_store=transfer_request_data_store or InMemoryDataStore())

    @property
    def ContainersData(self) -> ContainerDataStore:
        return self._containers_data_store

    @property
    def LocationsData(self):
        return self._locs_data_store

    @property
    def TransferRequestsData(self):
        return self._transfer_requests_data_store

    def clear(self):
        self._locs_data_store.clear()
        self._containers_data_store.clear()
        self._transfer_requests_data_store.clear()
