"""create exam_answers table

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "exam_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_id", sa.String(255), nullable=False),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_exam_answers_exam_id", "exam_answers", ["exam_id"])
    op.create_index(
        "ix_exam_answers_exam_student", "exam_answers", ["exam_id", "student_id"]
    )
    op.create_unique_constraint(
        "uq_exam_answers_exam_student_question",
        "exam_answers",
        ["exam_id", "student_id", "question_id"],
    )


def downgrade() -> None:
    op.drop_table("exam_answers")
