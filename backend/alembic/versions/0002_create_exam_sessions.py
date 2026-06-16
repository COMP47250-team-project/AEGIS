"""create exam_sessions and exam_enrollments tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "quiz_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quizzes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("course_id", sa.String(255), nullable=False),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_exam_sessions_quiz_id", "exam_sessions", ["quiz_id"])
    op.create_index("ix_exam_sessions_course_id", "exam_sessions", ["course_id"])
    op.create_index("ix_exam_sessions_state", "exam_sessions", ["state"])

    op.create_table(
        "exam_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "exam_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_id", sa.String(255), nullable=False),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_exam_enrollments_exam_id", "exam_enrollments", ["exam_id"])
    op.create_unique_constraint(
        "uq_exam_enrollments_exam_student",
        "exam_enrollments",
        ["exam_id", "student_id"],
    )


def downgrade() -> None:
    op.drop_table("exam_enrollments")
    op.drop_index("ix_exam_sessions_state", "exam_sessions")
    op.drop_index("ix_exam_sessions_course_id", "exam_sessions")
    op.drop_index("ix_exam_sessions_quiz_id", "exam_sessions")
    op.drop_table("exam_sessions")
