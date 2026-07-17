from coopstorage.storage.loc_load.data.sql.sql_layout_data_store import SqlLayoutDataStore, LayoutRecord
from .db import get_session


class SqliteLayoutDataStore(SqlLayoutDataStore):
    def __init__(self):
        super().__init__(get_session)


__all__ = ['SqliteLayoutDataStore', 'LayoutRecord']
