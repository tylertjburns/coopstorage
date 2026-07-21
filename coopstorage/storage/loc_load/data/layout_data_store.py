from datetime import datetime
from typing import Callable, List, Optional, Protocol
from uuid import UUID

from pydantic import BaseModel

from cooptools.dataStore.dataStoreProtocol import DataStoreProtocol


class LayoutRecord(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    location_count: int = 0

    model_config = {'from_attributes': True}


class LayoutDataStore(Protocol):
    """Layout CRUD, independent of backend (SQL, in-memory, etc.)."""

    def create(self, name: str, description: Optional[str] = None) -> LayoutRecord: ...

    def get_all(self) -> List[LayoutRecord]: ...

    def get(self, layout_id) -> Optional[LayoutRecord]: ...

    def update(
        self,
        layout_id,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[LayoutRecord]: ...

    def delete(self, layout_id) -> None: ...


LocationDataStoreFactory = Callable[[str], DataStoreProtocol]
