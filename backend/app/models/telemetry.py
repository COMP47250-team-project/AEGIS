import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

_EXAM_SESSIONS_FK = "exam_sessions.id"


class TelemetryEvent(Base):
    """Raw browser telemetry captured during an exam session.

    One row per discrete browser event (tab_hidden, paste, focus_lost, etc.).
    The JSON payload stores event-specific metadata; the PostgreSQL migration
    uses JSONB for GIN-index query performance.
    """

    __tablename__ = "telemetry_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(_EXAM_SESSIONS_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    exam_session: Mapped["object"] = relationship(
        "ExamSession",
        backref="telemetry_events",
        foreign_keys=[exam_id],
    )


class StudentBaseline(Base):
    """Per-student typing baseline, computed from early-exam keystrokes.

    Used by the signal scorer to detect anomalous keystroke rhythm.
    One row per (exam, student); upserted when enough keystrokes are collected.
    """

    __tablename__ = "student_baselines"
    __table_args__ = (
        UniqueConstraint(
            "exam_id", "student_id", name="uq_student_baselines_exam_student"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(_EXAM_SESSIONS_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False)
    mean_keystroke_interval_ms: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    keystroke_stddev_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    exam_session: Mapped["object"] = relationship(
        "ExamSession",
        backref="student_baselines",
        foreign_keys=[exam_id],
    )


class SessionScore(Base):
    """Integrity confidence score for one student in one exam.

    Stores a sub-score (0–1) for each of the six behavioural signals and
    an aggregate integrity_score (0–1, higher = more suspicious).
    Produced by the async scoring service after the exam is closed.
    """

    __tablename__ = "session_scores"
    __table_args__ = (
        UniqueConstraint(
            "exam_id", "student_id", name="uq_session_scores_exam_student"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(_EXAM_SESSIONS_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tab_switch_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    paste_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    keystroke_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    focus_loss_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    answer_timing_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    copy_sequence_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    integrity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    exam_session: Mapped["object"] = relationship(
        "ExamSession",
        backref="session_scores",
        foreign_keys=[exam_id],
    )
