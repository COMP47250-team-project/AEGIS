"""create student_sessions table

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "exam_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_id", sa.String(255), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_student_sessions_exam_id", "student_sessions", ["exam_id"])
    op.create_unique_constraint(
        "uq_student_sessions_exam_student",
        "student_sessions",
        ["exam_id", "student_id"],
    )


def downgrade() -> None:
    op.drop_table("student_sessions")
