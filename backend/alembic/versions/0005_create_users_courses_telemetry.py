"""create users, courses, telemetry_events, student_baselines, session_scores

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="student"),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # courses
    # ------------------------------------------------------------------
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_courses_code", "courses", ["code"], unique=True)

    # ------------------------------------------------------------------
    # telemetry_events  (payload stored as JSONB for GIN-index support)
    # ------------------------------------------------------------------
    op.create_table(
        "telemetry_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "exam_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_telemetry_events_exam_id", "telemetry_events", ["exam_id"])
    op.create_index(
        "ix_telemetry_events_student_id", "telemetry_events", ["student_id"]
    )
    op.create_index(
        "ix_telemetry_events_occurred_at", "telemetry_events", ["occurred_at"]
    )

    # ------------------------------------------------------------------
    # student_baselines
    # ------------------------------------------------------------------
    op.create_table(
        "student_baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "exam_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_id", sa.String(255), nullable=False),
        sa.Column("mean_keystroke_interval_ms", sa.Float(), nullable=True),
        sa.Column("keystroke_stddev_ms", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_student_baselines_exam_id", "student_baselines", ["exam_id"])
    op.create_unique_constraint(
        "uq_student_baselines_exam_student",
        "student_baselines",
        ["exam_id", "student_id"],
    )

    # ------------------------------------------------------------------
    # session_scores  (one row per student per exam after scoring)
    # ------------------------------------------------------------------
    op.create_table(
        "session_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "exam_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_id", sa.String(255), nullable=False),
        # Six signal components
        sa.Column("tab_switch_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("paste_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("keystroke_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("focus_loss_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "answer_timing_score", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "copy_sequence_score", sa.Float(), nullable=False, server_default="0"
        ),
        # Aggregate
        sa.Column("integrity_score", sa.Float(), nullable=False, server_default="0"),
        # Optional reviewer annotation
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_session_scores_exam_id", "session_scores", ["exam_id"])
    op.create_unique_constraint(
        "uq_session_scores_exam_student",
        "session_scores",
        ["exam_id", "student_id"],
    )


def downgrade() -> None:
    op.drop_table("session_scores")
    op.drop_table("student_baselines")
    op.drop_table("telemetry_events")
    op.drop_table("courses")
    op.drop_table("users")
