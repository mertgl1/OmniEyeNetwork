"""Create the baseline OmniEye schema when a database is empty.

Existing installations created by SQLAlchemy's create_all are detected and
left intact, then recorded as the baseline revision.
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "device_groups" not in existing:
        op.create_table(
            "device_groups",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_device_groups_name", "device_groups", ["name"], unique=True)

    if "devices" not in existing:
        op.create_table(
            "devices",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("hostname", sa.String(length=128), nullable=False),
            sa.Column("ip_address", sa.String(length=45), nullable=False),
            sa.Column("vendor", sa.String(length=50), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=True),
            sa.Column("os_type", sa.String(length=50), nullable=False),
            sa.Column("os_version", sa.String(length=100), nullable=True),
            sa.Column("ssh_port", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("encrypted_credentials", sa.Text(), nullable=True),
            sa.Column("group_id", sa.Integer(), nullable=True),
            sa.Column("last_backup_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["group_id"], ["device_groups.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_devices_hostname", "devices", ["hostname"], unique=True)
        op.create_index("ix_devices_ip_address", "devices", ["ip_address"])
        op.create_index("ix_devices_vendor", "devices", ["vendor"])

    if "ports" not in existing:
        op.create_table(
            "ports",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("device_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("admin_status", sa.String(length=20), nullable=False),
            sa.Column("vlan", sa.Integer(), nullable=True),
            sa.Column("mac_address", sa.String(length=32), nullable=True),
            sa.Column("speed", sa.String(length=32), nullable=True),
            sa.Column("duplex", sa.String(length=32), nullable=True),
            sa.Column("last_change", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ports_device_id", "ports", ["device_id"])
        op.create_index("ix_ports_name", "ports", ["name"])
        op.create_index("ix_ports_mac_address", "ports", ["mac_address"])

    if "config_backups" not in existing:
        op.create_table(
            "config_backups",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("device_id", sa.Integer(), nullable=False),
            sa.Column("config_text", sa.Text(), nullable=False),
            sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("backup_type", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_config_backups_device_id", "config_backups", ["device_id"])
        op.create_index("ix_config_backups_checksum_sha256", "config_backups", ["checksum_sha256"])

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("display_name", sa.String(length=128), nullable=True),
            sa.Column("email", sa.String(length=128), nullable=True),
            sa.Column("hashed_password", sa.String(length=255), nullable=True),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("is_ad_user", sa.Boolean(), nullable=False),
            sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_username", "users", ["username"], unique=True)
        op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """Keep baseline data intact; this migration is deliberately non-destructive."""
