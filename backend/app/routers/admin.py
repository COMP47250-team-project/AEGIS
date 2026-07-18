"""Super-admin console endpoints (AEGIS-107).

Read-only visibility across all professors — all users, all exams, and the
system audit log — plus account deactivation. Every route requires the
super_admin role; professors and students get 403.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.audit import AuditLog
from app.models.exam import Enrollment, ExamSession
from app.models.quiz import Quiz
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AdminUser(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None


class AdminExam(BaseModel):
    exam_id: str
    title: str
    professor_email: str | None
    state: str
    student_count: int
    created_at: datetime


class AdminAuditEntry(BaseModel):
    event_type: str
    actor_email: str | None
    target_id: str | None
    timestamp: datetime
    details: dict


class Page(BaseModel):
    total: int
    limit: int
    offset: int


class AdminUserPage(Page):
    items: list[AdminUser]


class AdminExamPage(Page):
    items: list[AdminExam]


class AdminAuditPage(Page):
    items: list[AdminAuditEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _emails_for_ids(db: AsyncSession, ids: set[str]) -> dict[str, str]:
    """Map user-id strings to emails, skipping any that aren't valid UUIDs."""
    valid: list[uuid.UUID] = []
    for i in ids:
        try:
            valid.append(uuid.UUID(i))
        except (ValueError, TypeError):
            continue
    if not valid:
        return {}
    rows = await db.execute(select(User.id, User.email).where(User.id.in_(valid)))
    return {str(uid): email for uid, email in rows.all()}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/users", response_model=AdminUserPage)
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_role("super_admin")),
    role: Literal["student", "professor", "super_admin"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AdminUserPage:
    where = [User.role == role] if role else []
    total = await db.scalar(select(func.count()).select_from(User).where(*where))
    rows = await db.execute(
        select(User)
        .where(*where)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        AdminUser(
            id=str(u.id),
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            last_login=u.last_login,
        )
        for u in rows.scalars().all()
    ]
    return AdminUserPage(items=items, total=total or 0, limit=limit, offset=offset)


@router.get("/exams", response_model=AdminExamPage)
async def list_all_exams(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_role("super_admin")),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AdminExamPage:
    total = await db.scalar(select(func.count()).select_from(ExamSession))
    rows = await db.execute(
        select(ExamSession, Quiz)
        .join(Quiz, ExamSession.quiz_id == Quiz.id)
        .order_by(ExamSession.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    exams = rows.all()

    # Batch-resolve professor emails and enrolment counts for the page.
    emails = await _emails_for_ids(db, {exam.created_by for exam, _ in exams})
    counts: dict[uuid.UUID, int] = {}
    exam_ids = [exam.id for exam, _ in exams]
    if exam_ids:
        count_rows = await db.execute(
            select(Enrollment.exam_id, func.count())
            .where(Enrollment.exam_id.in_(exam_ids))
            .group_by(Enrollment.exam_id)
        )
        counts = {eid: n for eid, n in count_rows.all()}

    items = [
        AdminExam(
            exam_id=str(exam.id),
            title=quiz.title,
            professor_email=emails.get(exam.created_by),
            state=exam.state,
            student_count=counts.get(exam.id, 0),
            created_at=exam.created_at,
        )
        for exam, quiz in exams
    ]
    return AdminExamPage(items=items, total=total or 0, limit=limit, offset=offset)


@router.get("/audit", response_model=AdminAuditPage)
async def list_audit_log(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_role("super_admin")),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AdminAuditPage:
    total = await db.scalar(select(func.count()).select_from(AuditLog))
    rows = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    events = rows.scalars().all()

    actor_ids = {e.actor_id for e in events if e.actor_id is not None}
    emails = await _emails_for_ids(db, actor_ids)

    items = [
        AdminAuditEntry(
            event_type=e.event_type,
            actor_email=emails.get(e.actor_id) if e.actor_id else None,
            target_id=e.target_id,
            timestamp=e.created_at,
            details=e.audit_metadata,
        )
        for e in events
    ]
    return AdminAuditPage(items=items, total=total or 0, limit=limit, offset=offset)


@router.post("/users/{user_id}/deactivate", response_model=AdminUser)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_role("super_admin")),
) -> AdminUser:
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return AdminUser(
        id=str(user.id),
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.post("/users/{user_id}/activate", response_model=AdminUser)
async def activate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_role("super_admin")),
) -> AdminUser:
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return AdminUser(
        id=str(user.id),
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )
