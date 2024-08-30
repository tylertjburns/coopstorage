from coopstorage.storage2.loc_load.location import Location
from coopmongo.mongoCollectionDataStore import MongoCollectionDataStore, ObjectDocumentFacade
from cooptools.dataStore import dbConnectionURI as dburi
from cooptools.cnxn_info import Creds
from dataclasses import dataclass, field, asdict
from cooptools.dataStore.inMemoryDataStore import InMemoryDataStore
from cooptools.dataStore.dataStoreProtocol import DataStoreProtocol
from coopstorage.storage2.loc_load import dcs as dcs
from typing import Iterable
from coopstorage.storage2.loc_load.transferRequest import TransferRequest

LOCATIONS = 'locations'
LOADS = 'loads'
TRANSFER_REQUESTS = 'transfer_requests'
DB_NAME = 'storage'

@dataclass
class StorageDataStore:
    loads_data_store: DataStoreProtocol = field(default_factory=InMemoryDataStore)
    location_data_store: DataStoreProtocol = field(default_factory=InMemoryDataStore)
    transfer_request_data_store: DataStoreProtocol = field(default_factory=InMemoryDataStore)

    def clear(self):
        self.location_data_store.clear()
        self.loads_data_store.clear()
        self.transfer_request_data_store.clear()

    # def add_or_update(self,
    #                   loads: Iterable[dcs.Load] = None,
    #                   locations: Iterable[Location] = None,
    #                   transfer_requests: Iterable[transfer_request_data_store] = None):
    #     if loads is not None:
    #         self.location_data_store.add(items=[x.as_jsonable_dict() for x in locations])
    #
    #     if locations is not None:
    #         self.loads_data_store.add(items=[x.as_jsonable_dict() for x in loads])
    #
    #     if transfer_requests is not None:
    #         self.transfer_request_data_store.add(items=[x.as_jsonable_dict() for x in transfer_requests])



def mongo_connection_args():
    args = dburi.MongoDBConnectionArgs(
        db_type=dburi.DataBaseType.MONGODB,
        db_connector=dburi.DataBaseConnector.SRV,
        server_name='cluster0.bfcjjod.mongodb.net',
        creds=Creds(
            user="tylertjburns",
            pw="Chick3nCoopDissonanc3!"
        )
    )
    return args

LOCATION_FACADE = ObjectDocumentFacade(
    obj_to_doc_translator=Location.to_jsonable_dict,
    doc_to_obj_translator=Location.from_jsonable_dict
)

LOAD_FACADE = ObjectDocumentFacade(
    obj_to_doc_translator=lambda x: asdict(x),
    doc_to_obj_translator=lambda x: dcs.Load(**x)
)

TRANSFER_REQUEST_FACADE = ObjectDocumentFacade(
    obj_to_doc_translator=lambda x: x.to_jsonable_dict(x),
    doc_to_obj_translator=lambda x: x.from_jsonable_dict(x)
)

PROD_LOC_DATA = MongoCollectionDataStore(db_name=DB_NAME, collection_name=LOCATIONS, connection_args=mongo_connection_args(), facade=LOCATION_FACADE)
PROD_LOAD_DATA = MongoCollectionDataStore(db_name=DB_NAME, collection_name=LOADS, connection_args=mongo_connection_args(), facade=LOAD_FACADE)
PROD_TREQ_DATA = MongoCollectionDataStore(db_name=DB_NAME, collection_name=TRANSFER_REQUESTS, connection_args=mongo_connection_args(), facade=TRANSFER_REQUEST_FACADE)
TEST_LOC_DATA = MongoCollectionDataStore(db_name=DB_NAME, collection_name=f"{LOCATIONS}_TEST", connection_args=mongo_connection_args(), facade=LOCATION_FACADE)
TEST_LOAD_DATA = MongoCollectionDataStore(db_name=DB_NAME, collection_name=f"{LOADS}_TEST", connection_args=mongo_connection_args(), facade=LOAD_FACADE)
TEST_TREQ_DATA = MongoCollectionDataStore(db_name=DB_NAME, collection_name=f"{TRANSFER_REQUESTS}_TEST", connection_args=mongo_connection_args(), facade=TRANSFER_REQUEST_FACADE)

PROD_DATA = StorageDataStore(
    location_data_store=PROD_LOC_DATA,
    loads_data_store=PROD_LOAD_DATA,
    transfer_request_data_store=PROD_TREQ_DATA
)

TEST_DATA = StorageDataStore(
    location_data_store=TEST_LOC_DATA,
    loads_data_store=TEST_LOAD_DATA,
    transfer_request_data_store=TEST_TREQ_DATA
)


if __name__ == "__main__":
    import coopstorage.storage2.loc_load.dcs as dcs
    import coopstorage.storage2.loc_load.channel_processors as cps
    from pprint import pprint

    def t01():
        TEST_LOC_DATA.clear()

        loc = Location(
            id='abc',
            location_meta=dcs.LocationMeta(
                dims=(1, 1, 1),
                channel_processor=cps.FIFOFlowChannelProcessor()
            ),
            coords=(100, 100, 200)
        )

        results = TEST_LOC_DATA.add([loc.to_jsonable_dict()]).get()


        ret = [Location.from_jsonable_dict(data) for id, data in results.items()]
        pprint(ret)

    def t02():
        TEST_LOC_DATA.clear()

        loc = Location(
            id='abc',
            location_meta=dcs.LocationMeta(
                dims=(1, 1, 1),
                channel_processor=cps.FIFOFlowChannelProcessor(),
                capacity=3
            ),
            coords=(100, 100, 200),
        )

        results = TEST_LOC_DATA.add([loc.to_jsonable_dict()]).get(ids=[loc.Id])
        loc = Location.from_jsonable_dict(results[loc.Id])
        loc.store_loads(['l1', 'l2'])

        results = TEST_LOC_DATA.update([loc.to_jsonable_dict()]).get(ids=[loc.Id])
        loc = Location.from_jsonable_dict(results[loc.Id])
        pprint(loc)

    def t_loadtest():
        pass

    t01()
    t02()

