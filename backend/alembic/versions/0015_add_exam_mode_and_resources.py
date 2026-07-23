"""add exam mode + open-book resource tables (AEGIS-121)

Adds the open-book exam feature's schema:
  - exam_sessions.mode  — "closed_book" (default) | "open_book"
  - exam_resources       — the professor's curated resource allowlist
  - resource_access      — append-only per-student resource-open tracking

Idempotent / inspector-guarded so a re-run (or a DB already migrated by the
test harness's Base.metadata.create_all) is a no-op, mirroring 0014.

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    exam_columns = {c["name"] for c in inspector.get_columns("exam_sessions")}
    if "mode" not in exam_columns:
        op.add_column(
            "exam_sessions",
            sa.Column(
                "mode",
                sa.String(20),
                nullable=False,
                server_default="closed_book",
            ),
        )

    if "exam_resources" not in inspector.get_table_names():
        op.create_table(
            "exam_resources",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "exam_id",
                sa.Uuid(),
                sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("type", sa.String(length=10), nullable=False),
            sa.Column("url", sa.Text(), nullable=True),
            sa.Column("blob_ref", sa.String(length=512), nullable=True),
            sa.Column(
                "embed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_exam_resources_exam_id", "exam_resources", ["exam_id"])

    if "resource_access" not in inspector.get_table_names():
        op.create_table(
            "resource_access",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "exam_id",
                sa.Uuid(),
                sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("student_id", sa.String(length=255), nullable=False),
            sa.Column(
                "resource_id",
                sa.Uuid(),
                sa.ForeignKey("exam_resources.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_resource_access_exam_id", "resource_access", ["exam_id"])
        op.create_index(
            "ix_resource_access_student_id", "resource_access", ["student_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "resource_access" in inspector.get_table_names():
        op.drop_index("ix_resource_access_student_id", table_name="resource_access")
        op.drop_index("ix_resource_access_exam_id", table_name="resource_access")
        op.drop_table("resource_access")

    if "exam_resources" in inspector.get_table_names():
        op.drop_index("ix_exam_resources_exam_id", table_name="exam_resources")
        op.drop_table("exam_resources")

    exam_columns = {c["name"] for c in inspector.get_columns("exam_sessions")}
    if "mode" in exam_columns:
        op.drop_column("exam_sessions", "mode")
