"""Add inventory category to devices."""

from alembic import op
import sqlalchemy as sa

revision = "0004_device_type"
down_revision = "0003_port_last_discovered_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "devices" not in sa.inspect(bind).get_table_names():
        return

    columns = {column["name"] for column in sa.inspect(bind).get_columns("devices")}
    if "device_type" not in columns:
        op.add_column(
            "devices",
            sa.Column(
                "device_type",
                sa.String(length=32),
                nullable=False,
                server_default="switch",
            ),
        )
        op.create_index("ix_devices_device_type", "devices", ["device_type"])


def downgrade() -> None:
    bind = op.get_bind()
    if "devices" not in sa.inspect(bind).get_table_names():
        return

    columns = {column["name"] for column in sa.inspect(bind).get_columns("devices")}
    if "device_type" in columns:
        indexes = {index["name"] for index in sa.inspect(bind).get_indexes("devices")}
        if "ix_devices_device_type" in indexes:
            op.drop_index("ix_devices_device_type", table_name="devices")
        op.drop_column("devices", "device_type")
