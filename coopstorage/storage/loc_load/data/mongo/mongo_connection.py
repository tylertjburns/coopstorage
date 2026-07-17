import os

from cooptools.cnxn_info import Creds
from cooptools.dataStore import dbConnectionURI as dburi


def mongo_connection_args():
    return dburi.MongoDBConnectionArgs(
        db_type=dburi.DataBaseType.MONGODB,
        db_connector=dburi.DataBaseConnector.SRV,
        server_name=os.environ['MONGO_SERVER'],
        creds=Creds(
            user=os.environ['MONGO_USER'],
            pw=os.environ['MONGO_PW'],
        ),
    )
