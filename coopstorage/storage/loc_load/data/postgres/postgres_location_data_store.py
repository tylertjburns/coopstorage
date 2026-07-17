from coopstorage.storage.loc_load.data.sql.sql_location_data_store import SqlLocationDataStore
from .db import get_session


class PostgresLocationDataStore(SqlLocationDataStore):
    def __init__(self, layout_id: str):
        super().__init__(layout_id, get_session)
