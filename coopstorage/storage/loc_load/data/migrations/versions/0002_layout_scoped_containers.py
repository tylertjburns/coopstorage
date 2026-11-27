"""Scope containers to a layout: primary key (id, layout_id).

transfers.container_id loses its foreign key: a container moving between layouts
changes its key, so a transfer can't keep a reference to it. Deleting a layout now
cascades to its containers and transfers.

Both tables are recreated rather than altered, because the constraint names that
create_all generated vary by database and SQLite can't change a primary key in place.
Nothing writes to either table before this revision, so the migration refuses to run
if either one has rows rather than risk dropping data.

Revision ID: 0002_layout_scoped_containers
Revises: 0001_baseline
Create Date: 2026-11-27
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_layout_scoped_containers'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None

_NOW = sa.text('CURRENT_TIMESTAMP')


def _require_empty(*tables: str) -> None:
    bind = op.get_bind()
    for table in tables:
        count = bind.execute(sa.text(f'SELECT COUNT(*) FROM {table}')).scalar()
        if count:
            raise RuntimeError(f'{table} has {count} rows; this migration recreates it and only runs on an empty table')


def _drop_containers_and_transfers() -> None:
    _require_empty('transfers', 'containers')
    op.drop_table('transfers')
    op.drop_table('containers')


def _create_transfer_indexes() -> None:
    op.create_index('ix_transfers_status', 'transfers', ['status'])
    op.create_index('ix_transfers_container', 'transfers', ['container_id'])
    op.create_index('ix_transfers_source_layout', 'transfers', ['source_layout_id'])
    op.create_index('ix_transfers_dest_layout', 'transfers', ['dest_layout_id'])


def upgrade() -> None:
    _drop_containers_and_transfers()
    op.create_table(
        'containers',
        sa.Column('id', sa.String(255), nullable=False),
        sa.Column('layout_id', sa.Uuid(as_uuid=True),
                  sa.ForeignKey('layouts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('uom_name', sa.String(100)),
        sa.Column('weight', sa.Float),
        sa.Column('contents', sa.JSON),
        sa.Column('uom_capacities', sa.JSON),
        sa.Column('location_id', sa.String(255)),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW),
        sa.PrimaryKeyConstraint('id', 'layout_id', name='pk_containers'),
    )
    op.create_index('ix_containers_placement', 'containers', ['location_id', 'layout_id'])
    op.create_table(
        'transfers',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('source_location_id', sa.String(255)),
        sa.Column('source_layout_id', sa.Uuid(as_uuid=True), sa.ForeignKey('layouts.id', ondelete='CASCADE')),
        sa.Column('dest_location_id', sa.String(255)),
        sa.Column('dest_layout_id', sa.Uuid(as_uuid=True), sa.ForeignKey('layouts.id', ondelete='CASCADE')),
        sa.Column('container_id', sa.String(255)),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('criteria', sa.JSON),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
    )
    _create_transfer_indexes()


def downgrade() -> None:
    _drop_containers_and_transfers()
    op.create_table(
        'containers',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('uom_name', sa.String(100)),
        sa.Column('weight', sa.Float),
        sa.Column('contents', sa.JSON),
        sa.Column('uom_capacities', sa.JSON),
        sa.Column('location_id', sa.String(255)),
        sa.Column('layout_id', sa.Uuid(as_uuid=True), sa.ForeignKey('layouts.id')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW),
    )
    op.create_index('ix_containers_placement', 'containers', ['location_id', 'layout_id'])
    op.create_table(
        'transfers',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('source_location_id', sa.String(255)),
        sa.Column('source_layout_id', sa.Uuid(as_uuid=True), sa.ForeignKey('layouts.id')),
        sa.Column('dest_location_id', sa.String(255)),
        sa.Column('dest_layout_id', sa.Uuid(as_uuid=True), sa.ForeignKey('layouts.id')),
        sa.Column('container_id', sa.String(255), sa.ForeignKey('containers.id')),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('criteria', sa.JSON),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
    )
    _create_transfer_indexes()
