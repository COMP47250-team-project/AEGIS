import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class RiskFlag(Base):
    __tablename__ = "risk_flags"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    threshold_triggered: Mapped[str] = mapped_column(
        String(20), nullable=False, default="HIGH"
    )
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    flagged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

