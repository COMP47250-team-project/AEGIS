"""add audit_log table and users.last_login (AEGIS-107)

Adds the super-admin audit trail table and a last_login timestamp on users.
Idempotent: guards on existing table/column so a re-run is a no-op.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "audit_log" not in inspector.get_table_names():
        op.create_table(
            "audit_log",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("actor_id", sa.String(length=255), nullable=True),
            sa.Column("target_id", sa.String(length=255), nullable=True),
            sa.Column(
                "metadata",
                postgresql.JSONB(),
                nullable=False,
                server_default="{}",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])
        op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "last_login" not in user_columns:
        op.add_column(
            "users",
            sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "last_login" in user_columns:
        op.drop_column("users", "last_login")

    if "audit_log" in inspector.get_table_names():
        op.drop_index("ix_audit_log_created_at", table_name="audit_log")
        op.drop_index("ix_audit_log_event_type", table_name="audit_log")
        op.drop_table("audit_log")
