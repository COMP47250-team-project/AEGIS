import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.exam import Enrollment, ExamAnswer, ExamSession, StudentSession
from app.schemas.exam import (
    AnswerItemRead,
    AnswerSubmit,
    AnswerSubmitResponse,
    EnrollmentCreate,
    EnrollmentRead,
    ExamCreate,
    ExamRead,
    StudentSessionRead,
)
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


@router.get("", response_model=list[ExamRead])
async def list_exams(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[ExamRead]:
    result = await db.execute(
        select(ExamSession)
        .where(ExamSession.created_by == user_id)
        .order_by(ExamSession.created_at.desc())
    )
    exams = result.scalars().all()
    return [ExamRead.from_orm_with_count(e, 0) for e in exams]


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
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student is already enrolled in this exam session",
        )
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
# Answer submission (AEGIS-35)
# ---------------------------------------------------------------------------


@router.post("/{exam_id}/answers", response_model=AnswerSubmitResponse)
async def submit_answers(
    exam_id: uuid.UUID,
    body: AnswerSubmit,
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(get_current_user_id),
) -> AnswerSubmitResponse:
    """Durably persist student answers.

    Critical invariant: answers are committed to PostgreSQL before any
    side effects. This endpoint MUST NOT fail due to WebSocket or Service
    Bus unavailability — those are secondary concerns.
    """
    exam = await _get_exam_or_404(db, exam_id)
    if exam.state != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Answers can only be submitted while the exam is open",
        )

    now = datetime.now(timezone.utc)
    saved: list[ExamAnswer] = []

    for item in body.answers:
        result = await db.execute(
            select(ExamAnswer).where(
                ExamAnswer.exam_id == exam_id,
                ExamAnswer.student_id == student_id,
                ExamAnswer.question_id == item.question_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.answer = item.answer
            existing.saved_at = now
            saved.append(existing)
        else:
            new_answer = ExamAnswer(
                exam_id=exam_id,
                student_id=student_id,
                question_id=item.question_id,
                answer=item.answer,
                saved_at=now,
            )
            db.add(new_answer)
            saved.append(new_answer)

    # Commit DB writes unconditionally — this is the durable store.
    await db.commit()

    for answer in saved:
        await db.refresh(answer)

    answer_reads = [AnswerItemRead.model_validate(a) for a in saved]
    return AnswerSubmitResponse(saved=len(saved), answers=answer_reads)


# ---------------------------------------------------------------------------
# Student session / GDPR consent (AEGIS-38)
# ---------------------------------------------------------------------------


@router.get("/{exam_id}/session", response_model=StudentSessionRead)
async def get_student_session(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(get_current_user_id),
) -> StudentSessionRead:
    """Return (or lazily create) the student session for an exam.

    Used by the frontend to check whether the student has already consented.
    The session row is created with consent_at=NULL on first access, so the
    consent screen is always shown on a fresh navigation.
    """
    await _get_exam_or_404(db, exam_id)

    result = await db.execute(
        select(StudentSession).where(
            StudentSession.exam_id == exam_id,
            StudentSession.student_id == student_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        session = StudentSession(exam_id=exam_id, student_id=student_id)
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return StudentSessionRead.model_validate(session)


@router.post("/{exam_id}/consent", response_model=StudentSessionRead)
async def record_consent(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(get_current_user_id),
) -> StudentSessionRead:
    """Record the student's GDPR consent for monitoring.

    Sets consent_at to the current UTC timestamp. Idempotent — calling it
    again simply updates the timestamp.
    """
    await _get_exam_or_404(db, exam_id)

    result = await db.execute(
        select(StudentSession).where(
            StudentSession.exam_id == exam_id,
            StudentSession.student_id == student_id,
        )
    )
    session = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if session is None:
        session = StudentSession(exam_id=exam_id, student_id=student_id, consent_at=now)
        db.add(session)
    else:
        session.consent_at = now

    await db.commit()
    await db.refresh(session)
    return StudentSessionRead.model_validate(session)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_exam_or_404(db: AsyncSession, exam_id: uuid.UUID) -> ExamSession:
    result = await db.execute(select(ExamSession).where(ExamSession.id == exam_id))
    exam = result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exam session not found"
        )
    return exam


async def _enrollment_count(db: AsyncSession, exam_id: uuid.UUID) -> int:
    result = await db.execute(select(func.count()).where(Enrollment.exam_id == exam_id))
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
