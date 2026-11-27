"""Baseline: the schema as metadata.create_all built it before migrations existed.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-27
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None

_NOW = sa.text('CURRENT_TIMESTAMP')


def upgrade() -> None:
    op.create_table(
        'layouts',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW),
        sa.UniqueConstraint('name', name='uq_layouts_name'),
    )
    op.create_table(
        'channels',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('processor_type', sa.String(100), nullable=False),
        sa.Column('capacity', sa.Integer, nullable=False),
        sa.Column('channel_axis', sa.Integer, nullable=False),
        sa.Column('slots', sa.JSON, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW),
    )
    op.create_table(
        'locations',
        sa.Column('id', sa.String(255), nullable=False),
        sa.Column('layout_id', sa.Uuid(as_uuid=True),
                  sa.ForeignKey('layouts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('x', sa.Float, nullable=False),
        sa.Column('y', sa.Float, nullable=False),
        sa.Column('z', sa.Float, nullable=False),
        sa.Column('dim_x', sa.Float, nullable=False),
        sa.Column('dim_y', sa.Float, nullable=False),
        sa.Column('dim_z', sa.Float, nullable=False),
        sa.Column('delete_on_receive', sa.Boolean, nullable=False),
        sa.Column('channel_id', sa.Uuid(as_uuid=True), sa.ForeignKey('channels.id'), nullable=False),
        sa.Column('zone', sa.String(255)),
        sa.Column('aisle', sa.String(255)),
        sa.Column('row', sa.String(255)),
        sa.Column('bay', sa.String(255)),
        sa.Column('shelf', sa.String(255)),
        sa.Column('extra_labels', sa.JSON),
        sa.PrimaryKeyConstraint('id', 'layout_id', name='pk_locations'),
    )
    op.create_index('ix_locations_layout', 'locations',
                    ['layout_id', 'id', 'x', 'y', 'z', 'channel_id'])
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
    op.create_index('ix_transfers_status', 'transfers', ['status'])
    op.create_index('ix_transfers_container', 'transfers', ['container_id'])
    op.create_index('ix_transfers_source_layout', 'transfers', ['source_layout_id'])
    op.create_index('ix_transfers_dest_layout', 'transfers', ['dest_layout_id'])
    op.create_table(
        'heatmap_events',
        sa.Column('id', sa.BigInteger, autoincrement=True, primary_key=True),
        sa.Column('layout_id', sa.Uuid(as_uuid=True), sa.ForeignKey('layouts.id'), nullable=False),
        sa.Column('location_id', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )
    op.create_index('ix_heatmap_query', 'heatmap_events', ['layout_id', 'location_id', 'occurred_at'])


def downgrade() -> None:
    for table in ('heatmap_events', 'transfers', 'containers', 'locations', 'channels', 'layouts'):
        op.drop_table(table)
