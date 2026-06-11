import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("quizzes.id", ondelete="RESTRICT"), nullable=False
    )
    course_id: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # State machine: draft → open → closed
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    enrollments: Mapped[list["Enrollment"]] = relationship(
        "Enrollment",
        back_populates="exam",
        cascade="all, delete-orphan",
    )


class Enrollment(Base):
    __tablename__ = "exam_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    exam: Mapped["ExamSession"] = relationship("ExamSession", back_populates="enrollments")
