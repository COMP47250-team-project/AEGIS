"""Course management endpoints — create courses and manage enrollments."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.course import Course
from app.models.user import User

router = APIRouter(prefix="/courses", tags=["courses"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class CourseCreate(BaseModel):
    title: str
    code: str
    description: str | None = None


class CourseResponse(BaseModel):
    id: uuid.UUID
    title: str
    code: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EnrollRequest(BaseModel):
    code: str


class StudentResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None

    model_config = {"from_attributes": True}


# ── In-memory enrollment store (until Alembic migration adds the table) ──────
# Maps course_id -> set of student_ids
_enrollments: dict[uuid.UUID, set[str]] = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────


# POST /courses — professor creates a course
@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> Course:
    # Check code uniqueness
    existing = await db.scalar(select(Course).where(Course.code == payload.code))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course code already exists",
        )
    course = Course(
        title=payload.title,
        code=payload.code,
        description=payload.description,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


# GET /courses/{id}/students — professor views enrolled students
# TODO(AEGIS-27): restrict to professor role once JWT middleware is merged
@router.get("/{course_id}/students", response_model=list[StudentResponse])
async def get_enrolled_students(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> list[User]:
    course = await db.scalar(select(Course).where(Course.id == course_id))
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    student_ids = _enrollments.get(course_id, set())
    if not student_ids:
        return []
    result = await db.scalars(
        select(User).where(User.id.in_([uuid.UUID(sid) for sid in student_ids]))
    )
    return list(result.all())


# POST /courses/{id}/enroll — student self-enrolls via access code
@router.post("/{course_id}/enroll", status_code=status.HTTP_200_OK)
async def enroll_student(
    course_id: uuid.UUID,
    payload: EnrollRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    course = await db.scalar(select(Course).where(Course.id == course_id))
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    if course.code != payload.code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid access code",
        )
    # Idempotent — return 200 if already enrolled
    if course_id not in _enrollments:
        _enrollments[course_id] = set()
    _enrollments[course_id].add(current_user_id)
    return {"detail": "Enrolled successfully"}


# DELETE /courses/{id}/students/{student_id} — professor removes student
@router.delete("/{course_id}/students/{student_id}", status_code=status.HTTP_200_OK)
async def remove_student(
    course_id: uuid.UUID,
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> dict[str, str]:
    if course_id not in _enrollments or str(student_id) not in _enrollments[course_id]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )
    _enrollments[course_id].discard(str(student_id))
    return {"detail": "Student removed successfully"}
