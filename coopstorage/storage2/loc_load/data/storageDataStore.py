from cooptools.dataStore.inMemoryDataStore import InMemoryDataStore
from cooptools.dataStore.dataStoreProtocol import DataStoreProtocol
import coopstorage.storage2.loc_load.qualifiers as qs
from typing import Self, List, Iterable, Dict
from coopstorage.storage2.loc_load import dcs
from coopstorage.storage2.loc_load.location import Location
from coopstorage.storage2.loc_load.transferRequest import TransferRequest
from cooptools.protocols import UniqueIdentifier

class LoadDataStore:
    def __init__(self,
                 data_store: DataStoreProtocol):
        self._data_store = data_store

    def get(self,
            ids: Iterable[UniqueIdentifier]=None,
            qualifier: qs.LoadQualifier=None) -> Dict[UniqueIdentifier, dcs.Load]:
        if qualifier is not None:
            ret = self._data_store.get(
                id_query=qualifier.pattern
            )
        else:
            ret = self._data_store.get(ids)

        ret = {k:v for k, v in ret.items() if qualifier.check_if_qualifies(v)}
        return ret

    def clear(self) -> Self:
        self._data_store.clear()
        return self

    def add(self, loads: Iterable[dcs.Load]):
        self._data_store.add(loads)
        return self

    def add_or_update(self, loads: Iterable[dcs.Load]):
        self._data_store.add_or_update(loads)
        return self

    def remove(self, loads: Iterable[dcs.Load]):
        self._data_store.remove(loads)
        return self

class LocationDataStore:
    def __init__(self,
                 data_store: DataStoreProtocol):
        self._data_store = data_store

    def get(self, qualifier: qs.LocationQualifier=None) -> Dict[UniqueIdentifier, Location]:
        if qualifier is not None:
            ret = self._data_store.get(
                id_query=qualifier.id_pattern
            )
            ret = {k: v for k, v in ret.items() if qualifier.check_if_qualifies(v)}
        else:
            ret = self._data_store.get()

        return ret

    def clear(self) -> Self:
        self._data_store.clear()
        return self

    def add(self, locs: Iterable[Location]):
        self._data_store.add(locs)
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
                 loads_data_store: DataStoreProtocol = None,
                 location_data_store: DataStoreProtocol = None,
                 transfer_request_data_store: DataStoreProtocol = None
                 ):
        self._loads_data_store: LoadDataStore = LoadDataStore(data_store=loads_data_store or InMemoryDataStore())
        self._locs_data_store: LocationDataStore = LocationDataStore(
            data_store=location_data_store or InMemoryDataStore())
        self._transfer_requests_data_store: TransferRequestDataStore = TransferRequestDataStore(
            data_store=transfer_request_data_store or InMemoryDataStore())

    @property
    def LoadsData(self) -> LoadDataStore:
        return self._loads_data_store

    @property
    def LocationsData(self):
        return self._locs_data_store

    @property
    def TransferRequestsData(self):
        return self._transfer_requests_data_store

    def clear(self):
        self._locs_data_store.clear()
        self._loads_data_store.clear()
        self._transfer_requests_data_store.clear()
