from typing import Iterable, Dict

from cooptools.protocols import IdentifiableProtocol, UniqueIdentifier

from coopstorage.storage2.loc_load.location import Location
from coopmongo.mongoCollectionDataStore import MongoCollectionDataStore
import coopmongo.mongo_utils as mutils


LOCATIONS = 'locations'
LOADS = 'loads'
DB_NAME = 'storage'

from cooptools.dataStore import dbConnectionURI as dburi
from cooptools.cnxn_info import Creds
from pprint import pprint

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
def mongo_collection_store_factory(db_name: str, collection_name: str) -> MongoCollectionDataStore:
    return MongoCollectionDataStore(
        db_name=db_name,
        collection_name=collection_name,
        connection_args=mongo_connection_args()
    )

PROD_LOC_DATA = mongo_collection_store_factory(db_name=DB_NAME, collection_name=LOCATIONS)
PROD_LOAD_DATA = mongo_collection_store_factory(db_name=DB_NAME, collection_name=LOADS)
TEST_LOC_DATA = mongo_collection_store_factory(db_name=DB_NAME, collection_name=f"{LOCATIONS}_TEST")
TEST_LOAD_DATA = mongo_collection_store_factory(db_name=DB_NAME, collection_name=f"{LOADS}_TEST")

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


    t01()
    t02()

