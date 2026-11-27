import os
import tempfile
import unittest
import uuid

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from coopstorage.storage.loc_load.data import migrations
from coopstorage.storage.loc_load.data.sql.tables import metadata


class TestMigrations(unittest.TestCase):

    def setUp(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.engine = create_engine(f'sqlite:///{path}')
        self.addCleanup(os.remove, path)
        self.addCleanup(self.engine.dispose)

    def _schema_diff(self):
        with self.engine.connect() as conn:
            return compare_metadata(MigrationContext.configure(conn), metadata)

    def _revision(self):
        with self.engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()

    def test_empty_database_upgrades_to_match_tables(self):
        migrations.upgrade(self.engine)
        self.assertEqual(self._schema_diff(), [])
        self.assertEqual(self._revision(), '0002_layout_scoped_containers')

    def test_pre_migration_database_is_stamped_then_upgraded(self):
        # Rebuild what the old create_all-based init_db left behind: baseline tables, no alembic_version.
        command.upgrade(migrations.alembic_config(self.engine), migrations.BASELINE_REVISION)
        with self.engine.begin() as conn:
            conn.execute(text('DROP TABLE alembic_version'))

        migrations.upgrade(self.engine)

        self.assertEqual(self._schema_diff(), [])
        self.assertEqual(self._revision(), '0002_layout_scoped_containers')

    def test_upgrade_is_idempotent(self):
        migrations.upgrade(self.engine)
        migrations.upgrade(self.engine)
        self.assertEqual(self._schema_diff(), [])

    def test_layout_scoping_refuses_to_drop_existing_containers(self):
        command.upgrade(migrations.alembic_config(self.engine), migrations.BASELINE_REVISION)
        layout_id = uuid.uuid4().hex
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO layouts (id, name) VALUES (:id, 'l1')"), {'id': layout_id})
            conn.execute(text("INSERT INTO containers (id, layout_id) VALUES ('c1', :id)"), {'id': layout_id})

        with self.assertRaisesRegex(RuntimeError, 'containers has 1 rows'):
            migrations.upgrade(self.engine)
        self.assertIn('containers', inspect(self.engine).get_table_names())

    def test_same_container_id_allowed_in_two_layouts(self):
        migrations.upgrade(self.engine)
        with self.engine.begin() as conn:
            for name in ('l1', 'l2'):
                layout_id = uuid.uuid4().hex
                conn.execute(text("INSERT INTO layouts (id, name) VALUES (:id, :name)"),
                             {'id': layout_id, 'name': name})
                conn.execute(text("INSERT INTO containers (id, layout_id) VALUES ('c1', :id)"), {'id': layout_id})
            self.assertEqual(conn.execute(text('SELECT COUNT(*) FROM containers')).scalar(), 2)


if __name__ == '__main__':
    unittest.main()
