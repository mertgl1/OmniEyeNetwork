"""Track the latest successful port inventory discovery."""

from alembic import op
import sqlalchemy as sa

revision = "0003_port_last_discovered_at"
down_revision = "0002_backup_retention_index"
branch_labels = None
depends_on = None

COLUMN_NAME = "last_discovered_at"


def upgrade() -> None:
    bind = op.get_bind()
    if "ports" not in sa.inspect(bind).get_table_names():
        return
    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("ports")
    }
    if COLUMN_NAME not in columns:
        op.add_column(
            "ports",
            sa.Column(COLUMN_NAME, sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "ports" not in sa.inspect(bind).get_table_names():
        return
    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("ports")
    }
    if COLUMN_NAME in columns:
        op.drop_column("ports", COLUMN_NAME)
