"""Audit-log writes for super-admin review (AEGIS-107).

Callers add an event to the current session; the surrounding request/transaction
is responsible for committing (so an audit write can't commit half-done work).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

# Event type constants — keep in sync with the admin console's icon map.
USER_REGISTERED = "user_registered"
EXAM_CREATED = "exam_created"
EXAM_OPENED = "exam_opened"
EXAM_CLOSED = "exam_closed"
STUDENT_FLAGGED = "student_flagged"


def record_audit_event(
    db: AsyncSession,
    event_type: str,
    *,
    actor_id: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Stage an audit event on the session (does not commit)."""
    db.add(
        AuditLog(
            event_type=event_type,
            actor_id=actor_id,
            target_id=target_id,
            audit_metadata=metadata or {},
        )
    )
