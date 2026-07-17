import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import require_role
from app.models.group import GroupMember, StudentGroup
from app.models.user import INVITED_PASSWORD, User
from app.schemas.groups import (
    GroupCreate,
    GroupDetail,
    GroupMemberUpdate,
    GroupSummary,
    InviteResult,
    InviteStudents,
    MemberRead,
    SkippedEmail,
    ValidateEmails,
    ValidationResult,
)

router = APIRouter(prefix="/groups", tags=["groups"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def _students_by_email(db: AsyncSession, emails: list[str]) -> list[User]:
    """Resolve emails to student users. Unknown emails are silently skipped."""
    wanted = {e.strip().lower() for e in emails if e.strip()}
    if not wanted:
        return []
    result = await db.execute(select(User).where(User.role == "student"))
    return [u for u in result.scalars().all() if u.email.lower() in wanted]


async def _classify_emails(
    db: AsyncSession, emails: list[str], existing_ids: set[str] | None = None
) -> tuple[list[User], list[SkippedEmail]]:
    """Match emails to registered students; report each skipped email with one reason.

    existing_ids: student ids already in the group (flagged "already in the group").
    """
    existing_ids = existing_ids or set()
    students = {
        u.email.lower(): u
        for u in (
            await db.execute(select(User).where(User.role == "student"))
        ).scalars().all()
    }
    seen: set[str] = set()
    add: list[User] = []
    skipped: list[SkippedEmail] = []
    for raw in emails:
        e = raw.strip()
        if not e:
            continue
        low = e.lower()
        if not _EMAIL_RE.match(e):
            reason = "not a valid email address"
        elif low in seen:
            reason = "duplicate in list"
        elif low not in students:
            reason = "no registered student with this email"
        elif str(students[low].id) in existing_ids:
            reason = "already in the group"
        else:
            seen.add(low)
            add.append(students[low])
            continue
        skipped.append(SkippedEmail(email=e, reason=reason))
    return add, skipped


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
        # session uses expire_on_commit=False, so force a refresh of the
        # already-loaded members collection after add/remove commits.
        .execution_options(populate_existing=True)
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
    to_add, skipped = await _classify_emails(db, body.student_emails)
    for u in to_add:
        db.add(GroupMember(group_id=group.id, student_id=str(u.id)))
    await db.commit()
    group = await _owned_group_or_404(db, group.id, professor_id)
    return GroupDetail(
        id=group.id, name=group.name, created_at=group.created_at,
        members=await _members(db, group), skipped=skipped,
    )


@router.post("/validate", response_model=ValidationResult)
async def validate_emails(
    body: ValidateEmails,
    db: AsyncSession = Depends(get_db),
    professor_id: str = Depends(require_role("professor")),
) -> ValidationResult:
    """Dry run: report which emails would be added vs skipped, without saving.

    Lets the UI warn about failures (typos, unknown students) before creating.
    """
    existing_ids: set[str] = set()
    if body.group_id is not None:
        group = await _owned_group_or_404(db, body.group_id, professor_id)
        existing_ids = {m.student_id for m in group.members}
    to_add, skipped = await _classify_emails(db, body.student_emails, existing_ids)
    return ValidationResult(
        matched=[
            MemberRead(student_id=str(u.id), email=u.email, name=u.full_name)
            for u in to_add
        ],
        skipped=skipped,
    )


def _name_from_email(email: str) -> str:
    """Best-effort display name from the local part, e.g. alice.smith -> Alice Smith."""
    local = email.split("@", 1)[0]
    return " ".join(p for p in re.split(r"[._-]+", local) if p).title() or local


@router.post("/invite-students", response_model=InviteResult)
async def invite_students(
    body: InviteStudents,
    db: AsyncSession = Depends(get_db),
    professor_id: str = Depends(require_role("professor")),
) -> InviteResult:
    """Create student accounts for valid emails that aren't registered yet.

    Invited accounts have no password until the student registers (claims) with
    the same email; they can be added to groups and enrolled in the meantime.
    """
    existing = {
        u.email.lower() for u in (await db.execute(select(User))).scalars().all()
    }
    seen: set[str] = set()
    created: list[MemberRead] = []
    skipped: list[SkippedEmail] = []
    for raw in body.emails:
        e = raw.strip()
        if not e:
            continue
        low = e.lower()
        if not _EMAIL_RE.match(e):
            skipped.append(SkippedEmail(email=e, reason="not a valid email address"))
        elif low in seen:
            skipped.append(SkippedEmail(email=e, reason="duplicate in list"))
        elif low in existing:
            skipped.append(SkippedEmail(email=e, reason="email already registered"))
        else:
            seen.add(low)
            user = User(
                email=e,
                hashed_password=INVITED_PASSWORD,
                role="student",
                full_name=_name_from_email(e),
            )
            db.add(user)
            await db.flush()
            created.append(
                MemberRead(student_id=str(user.id), email=user.email, name=user.full_name)
            )
    await db.commit()
    return InviteResult(created=created, skipped=skipped)


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


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    professor_id: str = Depends(require_role("professor")),
) -> None:
    # Members cascade (relationship delete-orphan + FK ON DELETE CASCADE).
    group = await _owned_group_or_404(db, group_id, professor_id)
    await db.delete(group)
    await db.commit()


@router.put("/{group_id}/members", response_model=GroupDetail)
async def update_members(
    group_id: uuid.UUID,
    body: GroupMemberUpdate,
    db: AsyncSession = Depends(get_db),
    professor_id: str = Depends(require_role("professor")),
) -> GroupDetail:
    group = await _owned_group_or_404(db, group_id, professor_id)
    existing = {m.student_id for m in group.members}

    to_add, skipped = await _classify_emails(db, body.add, existing)
    for u in to_add:
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
        members=await _members(db, group), skipped=skipped,
    )
