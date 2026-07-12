"""create student_groups and group_members

Revision ID: 0010b
Revises: 0010
Create Date: 2026-07-04

NOTE: originally authored as 0010 off 0009 (AEGIS-105), the same id AEGIS-111
independently used. Re-chained as 0010b after 0010 to give a single linear head.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010b"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("professor_id", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_student_groups_professor_id", "student_groups", ["professor_id"]
    )

    op.create_table(
        "group_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("student_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_id", sa.String(255), nullable=False),
    )
    op.create_unique_constraint(
        "uq_group_members_group_student",
        "group_members",
        ["group_id", "student_id"],
    )


def downgrade() -> None:
    op.drop_table("group_members")
    op.drop_table("student_groups")
