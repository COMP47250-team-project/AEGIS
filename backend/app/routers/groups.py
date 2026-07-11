import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import require_role
from app.models.group import GroupMember, StudentGroup
from app.models.user import User
from app.schemas.groups import (
    GroupCreate,
    GroupDetail,
    GroupMemberUpdate,
    GroupSummary,
    MemberRead,
)

router = APIRouter(prefix="/groups", tags=["groups"])


async def _students_by_email(db: AsyncSession, emails: list[str]) -> list[User]:
    """Resolve emails to student users. Unknown emails are silently skipped."""
    wanted = {e.strip().lower() for e in emails if e.strip()}
    if not wanted:
        return []
    result = await db.execute(select(User).where(User.role == "student"))
    return [u for u in result.scalars().all() if u.email.lower() in wanted]


async def _members(db: AsyncSession, group: StudentGroup) -> list[MemberRead]:
    ids = [m.student_id for m in group.members]
    if not ids:
        return []
    users = (
        await db.execute(select(User).where(User.id.in_([uuid.UUID(i) for i in ids])))
    ).scalars().all()
    by_id = {str(u.id): u for u in users}
    out: list[MemberRead] = []
    for sid in ids:
        u = by_id.get(sid)
        out.append(MemberRead(student_id=sid, email=u.email if u else "", name=u.full_name if u else None))
    return out


async def _owned_group_or_404(
    db: AsyncSession, group_id: uuid.UUID, professor_id: str
) -> StudentGroup:
    result = await db.execute(
        select(StudentGroup)
        .where(StudentGroup.id == group_id)
        .options(selectinload(StudentGroup.members))
    )
    group = result.scalar_one_or_none()
    if group is None or group.professor_id != professor_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


@router.post("", response_model=GroupDetail, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    db: AsyncSession = Depends(get_db),
    professor_id: str = Depends(require_role("professor")),
) -> GroupDetail:
    group = StudentGroup(name=body.name, professor_id=professor_id)
    db.add(group)
    await db.flush()
    for u in await _students_by_email(db, body.student_emails):
        db.add(GroupMember(group_id=group.id, student_id=str(u.id)))
    await db.commit()
    group = await _owned_group_or_404(db, group.id, professor_id)
    return GroupDetail(
        id=group.id, name=group.name, created_at=group.created_at,
        members=await _members(db, group),
    )


@router.get("", response_model=list[GroupSummary])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    professor_id: str = Depends(require_role("professor")),
) -> list[GroupSummary]:
    result = await db.execute(
        select(StudentGroup)
        .where(StudentGroup.professor_id == professor_id)
        .options(selectinload(StudentGroup.members))
        .order_by(StudentGroup.created_at.desc())
    )
    return [
        GroupSummary(
            id=g.id, name=g.name, member_count=len(g.members), created_at=g.created_at
        )
        for g in result.scalars().all()
    ]


@router.get("/{group_id}", response_model=GroupDetail)
async def get_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    professor_id: str = Depends(require_role("professor")),
) -> GroupDetail:
    group = await _owned_group_or_404(db, group_id, professor_id)
    return GroupDetail(
        id=group.id, name=group.name, created_at=group.created_at,
        members=await _members(db, group),
    )


@router.put("/{group_id}/members", response_model=GroupDetail)
async def update_members(
    group_id: uuid.UUID,
    body: GroupMemberUpdate,
    db: AsyncSession = Depends(get_db),
    professor_id: str = Depends(require_role("professor")),
) -> GroupDetail:
    group = await _owned_group_or_404(db, group_id, professor_id)
    existing = {m.student_id for m in group.members}

    for u in await _students_by_email(db, body.add):
        if str(u.id) not in existing:
            db.add(GroupMember(group_id=group.id, student_id=str(u.id)))

    remove_ids = {str(u.id) for u in await _students_by_email(db, body.remove)}
    for m in group.members:
        if m.student_id in remove_ids:
            await db.delete(m)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
    group = await _owned_group_or_404(db, group_id, professor_id)
    return GroupDetail(
        id=group.id, name=group.name, created_at=group.created_at,
        members=await _members(db, group),
    )
