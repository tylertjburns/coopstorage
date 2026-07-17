import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import delete, func, insert, select, update

from .tables import layouts as layouts_table, locations as loc_table


class LayoutRecord(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    location_count: int = 0

    model_config = {'from_attributes': True}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class SqlLayoutDataStore:
    """
    Layout CRUD backed by any SQL database.

    session_factory: a zero-argument callable returning a context manager
    that yields a SQLAlchemy Session.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def create(self, name: str, description: Optional[str] = None) -> LayoutRecord:
        layout_id = uuid.uuid4()
        now = _now()
        with self._session_factory() as sess:
            sess.execute(insert(layouts_table).values(
                id=layout_id,
                name=name,
                description=description,
                created_at=now,
                updated_at=now,
            ))
        return LayoutRecord(
            id=layout_id, name=name, description=description,
            created_at=now, updated_at=now, location_count=0,
        )

    def get_all(self) -> List[LayoutRecord]:
        with self._session_factory() as sess:
            stmt = (
                select(
                    layouts_table,
                    func.count(loc_table.c.id).label('location_count'),
                )
                .outerjoin(loc_table, layouts_table.c.id == loc_table.c.layout_id)
                .group_by(layouts_table.c.id)
                .order_by(layouts_table.c.created_at)
            )
            rows = sess.execute(stmt).fetchall()
        return [
            LayoutRecord(
                id=row.id,
                name=row.name,
                description=row.description,
                created_at=row.created_at,
                updated_at=row.updated_at,
                location_count=row.location_count or 0,
            )
            for row in rows
        ]

    def get(self, layout_id) -> Optional[LayoutRecord]:
        uid = UUID(str(layout_id))
        with self._session_factory() as sess:
            row = sess.execute(
                select(layouts_table).where(layouts_table.c.id == uid)
            ).fetchone()
            if row is None:
                return None
            count = sess.execute(
                select(func.count()).where(loc_table.c.layout_id == uid)
            ).scalar() or 0
        return LayoutRecord(
            id=row.id,
            name=row.name,
            description=row.description,
            created_at=row.created_at,
            updated_at=row.updated_at,
            location_count=count,
        )

    def update(
        self,
        layout_id,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[LayoutRecord]:
        uid = UUID(str(layout_id))
        vals: dict = {'updated_at': _now()}
        if name is not None:
            vals['name'] = name
        if description is not None:
            vals['description'] = description
        with self._session_factory() as sess:
            sess.execute(
                update(layouts_table)
                .where(layouts_table.c.id == uid)
                .values(**vals)
            )
        return self.get(uid)

    def delete(self, layout_id) -> None:
        uid = UUID(str(layout_id))
        with self._session_factory() as sess:
            sess.execute(delete(layouts_table).where(layouts_table.c.id == uid))
