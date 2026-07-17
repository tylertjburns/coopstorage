import uuid
from sqlalchemy import (
    MetaData, Table, Column, String, Float, Integer, Boolean,
    JSON, DateTime, Text, BigInteger, ForeignKey, Index,
    PrimaryKeyConstraint, UniqueConstraint, Uuid, text as sa_text,
)

metadata = MetaData()

layouts = Table(
    'layouts', metadata,
    Column('id', Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column('name', String(255), nullable=False),
    Column('description', Text),
    Column('created_at', DateTime(timezone=True), server_default=sa_text('CURRENT_TIMESTAMP')),
    Column('updated_at', DateTime(timezone=True), server_default=sa_text('CURRENT_TIMESTAMP')),
    UniqueConstraint('name', name='uq_layouts_name'),
)

# Holds both static processor config and mutable slot state so slot updates
# never touch the static location row.
channels = Table(
    'channels', metadata,
    Column('id', Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column('processor_type', String(100), nullable=False),
    Column('capacity', Integer, nullable=False, default=1),
    Column('channel_axis', Integer, nullable=False, default=0),
    Column('slots', JSON, nullable=False),
    Column('updated_at', DateTime(timezone=True), server_default=sa_text('CURRENT_TIMESTAMP')),
)

locations = Table(
    'locations', metadata,
    Column('id', String(255), nullable=False),
    Column('layout_id', Uuid(as_uuid=True),
           ForeignKey('layouts.id', ondelete='CASCADE'), nullable=False),
    Column('x', Float, nullable=False),
    Column('y', Float, nullable=False),
    Column('z', Float, nullable=False),
    Column('dim_x', Float, nullable=False),
    Column('dim_y', Float, nullable=False),
    Column('dim_z', Float, nullable=False),
    Column('delete_on_receive', Boolean, nullable=False, default=False),
    Column('channel_id', Uuid(as_uuid=True),
           ForeignKey('channels.id'), nullable=False),
    Column('zone', String(255)),
    Column('aisle', String(255)),
    Column('row', String(255)),
    Column('bay', String(255)),
    Column('shelf', String(255)),
    Column('extra_labels', JSON),
    PrimaryKeyConstraint('id', 'layout_id', name='pk_locations'),
)

# Covering index for the dominant read pattern: all locations in a layout.
Index('ix_locations_layout', locations.c.layout_id,
      locations.c.id, locations.c.x, locations.c.y, locations.c.z, locations.c.channel_id)

containers = Table(
    'containers', metadata,
    Column('id', String(255), primary_key=True),
    Column('uom_name', String(100)),
    Column('weight', Float),
    Column('contents', JSON, default=list),
    Column('uom_capacities', JSON, default=list),
    Column('location_id', String(255)),
    Column('layout_id', Uuid(as_uuid=True), ForeignKey('layouts.id')),
    Column('updated_at', DateTime(timezone=True), server_default=sa_text('CURRENT_TIMESTAMP')),
)

Index('ix_containers_placement', containers.c.location_id, containers.c.layout_id)

transfers = Table(
    'transfers', metadata,
    Column('id', Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column('source_location_id', String(255)),
    Column('source_layout_id', Uuid(as_uuid=True), ForeignKey('layouts.id')),
    Column('dest_location_id', String(255)),
    Column('dest_layout_id', Uuid(as_uuid=True), ForeignKey('layouts.id')),
    Column('container_id', String(255), ForeignKey('containers.id')),
    Column('status', String(50), nullable=False, default='pending'),
    Column('criteria', JSON),
    Column('requested_at', DateTime(timezone=True), server_default=sa_text('CURRENT_TIMESTAMP'), nullable=False),
    Column('completed_at', DateTime(timezone=True)),
)

Index('ix_transfers_status', transfers.c.status)
Index('ix_transfers_container', transfers.c.container_id)
Index('ix_transfers_source_layout', transfers.c.source_layout_id)
Index('ix_transfers_dest_layout', transfers.c.dest_layout_id)

heatmap_events = Table(
    'heatmap_events', metadata,
    Column('id', BigInteger, autoincrement=True, primary_key=True),
    Column('layout_id', Uuid(as_uuid=True),
           ForeignKey('layouts.id'), nullable=False),
    Column('location_id', String(255), nullable=False),
    Column('event_type', String(50), nullable=False),
    Column('occurred_at', DateTime(timezone=True), server_default=sa_text('CURRENT_TIMESTAMP'), nullable=False),
)

Index('ix_heatmap_query',
      heatmap_events.c.layout_id,
      heatmap_events.c.location_id,
      heatmap_events.c.occurred_at)
