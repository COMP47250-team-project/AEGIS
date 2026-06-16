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
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # e.g. "tab_hidden" | "tab_visible" | "paste" | "focus_lost" | "focus_gained"
    # | "copy_sequence" | "keystroke_burst"
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # JSON works on all backends; PostgreSQL migration overrides to JSONB
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
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # Mean time between keystrokes in milliseconds during the baseline window
    mean_keystroke_interval_ms: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    # Standard deviation of keystroke intervals during the baseline window
    keystroke_stddev_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Number of keystrokes used to compute this baseline
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
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Six signal components (0 = normal, 1 = highly suspicious) ---
    # Signal 1: how often the student left the exam tab
    tab_switch_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Signal 2: unexpected paste events
    paste_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Signal 3: deviation from the student's own keystroke rhythm baseline
    keystroke_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Signal 4: window focus/blur events during the exam
    focus_loss_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Signal 5: suspiciously fast answers relative to question complexity
    answer_timing_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # Signal 6: detected Ctrl+A → Ctrl+C → Ctrl+V copy sequences
    copy_sequence_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # --- Aggregate (weighted combination of the six signals above) ---
    integrity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Reviewer notes; optional field for human annotation
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
