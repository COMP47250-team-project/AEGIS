import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.exam import Enrollment, ExamSession
from app.schemas.exam import EnrollmentCreate, EnrollmentRead, ExamCreate, ExamRead
from app.services.scoring import dispatch_score_job

router = APIRouter(prefix="/exams", tags=["exams"])

# Valid state transitions — maps current state → set of reachable states
_TRANSITIONS: dict[str, str] = {
    "draft": "open",
    "open": "closed",
}


# ---------------------------------------------------------------------------
# Exam CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
async def create_exam(
    body: ExamCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> ExamRead:
    exam = ExamSession(**body.model_dump(), created_by=user_id)
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    return ExamRead.model_validate(exam)


@router.get("/{exam_id}", response_model=ExamRead)
async def get_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> ExamRead:
    exam = await _get_exam_or_404(db, exam_id)
    count = await _enrollment_count(db, exam_id)
    return ExamRead.from_orm_with_count(exam, count)


# ---------------------------------------------------------------------------
# Enrollment (needed for open-guard check)
# ---------------------------------------------------------------------------

@router.post(
    "/{exam_id}/enrollments",
    response_model=EnrollmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_student(
    exam_id: uuid.UUID,
    body: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> Enrollment:
    exam = await _get_exam_or_404(db, exam_id)
    if exam.state != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Students can only be enrolled while the exam is in draft state",
        )
    enrollment = Enrollment(exam_id=exam.id, student_id=body.student_id)
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------

@router.post("/{exam_id}/open", response_model=ExamRead)
async def open_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> ExamRead:
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)

    # Idempotent — already open is fine
    if exam.state == "open":
        count = await _enrollment_count(db, exam_id)
        return ExamRead.from_orm_with_count(exam, count)

    _assert_transition(exam, target="open")

    count = await _enrollment_count(db, exam_id)
    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot open an exam session with no enrolled students",
        )

    exam.state = "open"
    exam.opened_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(exam)
    return ExamRead.from_orm_with_count(exam, count)


@router.post("/{exam_id}/close", response_model=ExamRead)
async def close_exam(
    exam_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> ExamRead:
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)

    # Idempotent — already closed is fine
    if exam.state == "closed":
        count = await _enrollment_count(db, exam_id)
        return ExamRead.from_orm_with_count(exam, count)

    _assert_transition(exam, target="closed")

    exam.state = "closed"
    exam.closed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(exam)

    # Dispatch score computation asynchronously — must not block the HTTP response
    background_tasks.add_task(dispatch_score_job, exam.id)

    count = await _enrollment_count(db, exam_id)
    return ExamRead.from_orm_with_count(exam, count)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_exam_or_404(db: AsyncSession, exam_id: uuid.UUID) -> ExamSession:
    result = await db.execute(select(ExamSession).where(ExamSession.id == exam_id))
    exam = result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam session not found")
    return exam


async def _enrollment_count(db: AsyncSession, exam_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(Enrollment.exam_id == exam_id)
    )
    return result.scalar_one()


def _assert_owner(exam: ExamSession, user_id: str) -> None:
    if exam.created_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owning professor can transition this exam session",
        )


def _assert_transition(exam: ExamSession, target: str) -> None:
    allowed_next = _TRANSITIONS.get(exam.state)
    if allowed_next != target:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot transition exam from '{exam.state}' to '{target}'. "
                f"Valid next state is '{allowed_next}'."
            ),
        )
