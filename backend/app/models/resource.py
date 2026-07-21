"""Open-book exam resources and per-student access tracking (AEGIS-121).

Two tables:
  exam_resources  — the professor's curated allowlist for an open-book exam
                    (a URL, or an uploaded file served from Blob Storage).
  resource_access — append-only, one row per time a student opens a resource.
                    Aggregated at read time into the professor's report; the
                    integrity scorer ignores it (evidence, not enforcement).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_EXAM_SESSIONS_FK = "exam_sessions.id"


class ExamResource(Base):
    """One allowlisted resource for an open-book exam.

    ``type`` is "url" (external link, ``url`` set) or "file" (uploaded doc,
    ``blob_ref`` set to a server-generated storage key). ``embed`` marks a URL
    the professor has confirmed renders inside an <iframe>; framing-blocked URLs
    stay embed=False and open in a new tab (still tracked).
    """

    __tablename__ = "exam_resources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(_EXAM_SESSIONS_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # "url" | "file"
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Server-generated storage key ("{exam_id}/{uuid4}.pdf") — never derived from
    # the uploaded filename, so it can't be used for path traversal.
    blob_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    embed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class ResourceAccess(Base):
    """One row per time a student opens a resource during an open-book exam.

    Append-only: ``opened_at`` is set on open; ``duration_ms`` is filled in on
    close/switch/submit (best-effort — a hard tab-close can drop the final
    duration). Order is ``ORDER BY opened_at``; open count is the row count;
    total time is ``SUM(duration_ms)``.
    """

    __tablename__ = "resource_access"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(_EXAM_SESSIONS_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("exam_resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
