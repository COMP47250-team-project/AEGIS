import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# JSONB in Postgres (production); plain JSON under SQLite (test suite).
_JSONType = JSONB().with_variant(JSON(), "sqlite")


class AuditLog(Base):
    """Append-only log of key system events for super-admin review (AEGIS-107).

    actor_id / target_id are stored as strings (user ids are UUIDs, but some
    targets are non-user ids such as exam ids); resolved to emails at read time.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audit_metadata: Mapped[dict] = mapped_column(
        "metadata", _JSONType, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
