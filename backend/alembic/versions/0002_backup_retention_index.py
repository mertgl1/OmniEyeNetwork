"""Index backup history for per-device retention and audit scans."""

from alembic import op
import sqlalchemy as sa

revision = "0002_backup_retention_index"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_config_backups_device_created_version"


def upgrade() -> None:
    bind = op.get_bind()
    if "config_backups" not in sa.inspect(bind).get_table_names():
        return
    indexes = {
        index["name"]
        for index in sa.inspect(bind).get_indexes("config_backups")
    }
    if INDEX_NAME not in indexes:
        op.create_index(
            INDEX_NAME,
            "config_backups",
            ["device_id", "created_at", "version"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "config_backups" not in sa.inspect(bind).get_table_names():
        return
    indexes = {
        index["name"]
        for index in sa.inspect(bind).get_indexes("config_backups")
    }
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name="config_backups")
