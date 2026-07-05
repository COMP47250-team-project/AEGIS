import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_db
from app.dependencies import require_role
from typing import Literal, cast

from app.models.exam import Enrollment, ExamAnswer, ExamSession, StudentSession
from app.models.quiz import Question, Quiz
from app.models.telemetry import SessionScore
from app.models.user import User
from app.schemas.exam import (
    AnswerItemRead,
    AnswerSubmit,
    AnswerSubmitResponse,
    EnrollmentByEmail,
    EnrollmentCreate,
    EnrollmentRead,
    ExamCreate,
    ExamGradeReport,
    ExamRead,
    GradeAnswerItem,
    QuestionForStudent,
    StudentGradeEntry,
    StudentSessionRead,
    BulkEnrollCreate, 
    BulkEnrollResult,
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
    user_id: str = Depends(require_role("professor")),
) -> ExamRead:
    exam = ExamSession(**body.model_dump(), created_by=user_id)
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    return ExamRead.model_validate(exam)


@router.get("", response_model=list[ExamRead])
async def list_exams(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> list[ExamRead]:
    result = await db.execute(
        select(ExamSession, Quiz)
        .join(Quiz, ExamSession.quiz_id == Quiz.id)
        .where(ExamSession.created_by == user_id)
        .order_by(ExamSession.created_at.desc())
    )
    rows = result.all()
    items: list[ExamRead] = []
    for exam, quiz in rows:
        count = await _enrollment_count(db, exam.id)
        items.append(ExamRead.from_orm_with_count(exam, count, quiz_title=quiz.title))
    return items


@router.get("/{exam_id}", response_model=ExamRead)
async def get_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_role("professor")),
) -> ExamRead:
    exam = await _get_exam_or_404(db, exam_id)
    count = await _enrollment_count(db, exam_id)
    quiz_title = await _get_quiz_title(db, exam.quiz_id)
    return ExamRead.from_orm_with_count(exam, count, quiz_title=quiz_title)


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


@router.get("/{exam_id}/enrollments", response_model=list[EnrollmentRead])
async def list_enrollments(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> list[Enrollment]:
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)
    result = await db.execute(select(Enrollment).where(Enrollment.exam_id == exam_id))
    return list(result.scalars().all())


@router.post(
    "/{exam_id}/enrollments",
    response_model=EnrollmentRead,
    status_code=status.HTTP_200_OK,
)
async def enroll_student(
    exam_id: uuid.UUID,
    body: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_role("professor")),
) -> Enrollment:
    exam = await _get_exam_or_404(db, exam_id)
    if exam.state != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Students can only be enrolled while the exam is in draft state",
        )
    existing_result = await db.execute(
        select(Enrollment).where(
            Enrollment.exam_id == exam_id,
            Enrollment.student_id == body.student_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing 
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


@router.post(
    "/{exam_id}/enroll-by-email",
    response_model=EnrollmentRead,
    status_code=status.HTTP_200_OK,
)
async def enroll_student_by_email(
    exam_id: uuid.UUID,
    body: EnrollmentByEmail,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_role("professor")),
) -> Enrollment:
    """Enroll a student by email address (convenience for UI)."""
    exam = await _get_exam_or_404(db, exam_id)
    if exam.state != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Students can only be enrolled while the exam is in draft state",
        )
    user_result = await db.execute(
        select(User).where(User.email == body.email, User.role == "student")
    )
    student = user_result.scalar_one_or_none()
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student found with that email address",
        )
    enrollment = Enrollment(exam_id=exam.id, student_id=str(student.id))
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


@router.delete(
    "/{exam_id}/enrollments/{student_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def unenroll_student(
    exam_id: uuid.UUID,
    student_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> None:
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)
    if exam.state != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot unenroll students once the exam is open or closed",
        )
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.exam_id == exam_id,
            Enrollment.student_id == student_id,
        )
    )
    enrollment = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found"
        )
    await db.delete(enrollment)
    await db.commit()

@router.post(
    "/{exam_id}/enroll",
    response_model=BulkEnrollResult,
    status_code=status.HTTP_200_OK,
)
async def bulk_enroll_students(
    exam_id: uuid.UUID,
    body: BulkEnrollCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_role("professor")),
) -> BulkEnrollResult:
    """
    Idempotently enroll one or more students by student_id.

    Duplicate IDs in the request body are deduplicated before hitting the DB.
    Already-enrolled students are counted as skipped, not errors — this makes
    the endpoint safe to call repeatedly with the same CSV without side effects.
    Exam must be in draft state.
    """
    exam = await _get_exam_or_404(db, exam_id)
    if exam.state != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Students can only be enrolled while the exam is in draft state",
        )

    # Deduplicate while preserving order
    unique_ids = list(dict.fromkeys(body.student_ids))

    if not unique_ids:
        return BulkEnrollResult(enrolled=0, skipped=0, invalid=[])

    # ON CONFLICT DO NOTHING — idempotent by design
    # pg_insert is already imported at the top of this file
    stmt = pg_insert(Enrollment).values([
        {"exam_id": exam_id, "student_id": sid} for sid in unique_ids
    ])
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["exam_id", "student_id"]
    )
    result = await db.execute(stmt)
    await db.commit()

    enrolled = result.rowcount if result.rowcount is not None else 0
    skipped = len(unique_ids) - enrolled

    return BulkEnrollResult(enrolled=enrolled, skipped=skipped, invalid=[])

# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


@router.post("/{exam_id}/open", response_model=ExamRead)
async def open_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
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
    user_id: str = Depends(require_role("professor")),
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
    student_id: str = Depends(require_role("student")),
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


@router.get("/{exam_id}/answers", response_model=list[AnswerItemRead])
async def get_my_answers(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(require_role("student")),
) -> list[ExamAnswer]:
    """Return the calling student's own saved answers for an exam.

    Lets the frontend rehydrate the exam on refresh / re-login so the student
    resumes with their previously saved answers instead of a blank restart.
    """
    await _get_exam_or_404(db, exam_id)
    result = await db.execute(
        select(ExamAnswer).where(
            ExamAnswer.exam_id == exam_id,
            ExamAnswer.student_id == student_id,
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Student session / GDPR consent (AEGIS-38)
# ---------------------------------------------------------------------------


@router.get("/{exam_id}/session", response_model=StudentSessionRead)
async def get_student_session(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(require_role("student")),
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
    student_id: str = Depends(require_role("student")),
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
# Questions for students (AEGIS-39)
# ---------------------------------------------------------------------------


@router.get("/{exam_id}/questions", response_model=list[QuestionForStudent])
async def get_exam_questions(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(require_role("student")),
) -> list[Question]:
    """Return the exam's questions — correct_answer is never included.

    Requires an open exam and a consented student session.
    """
    exam = await _get_exam_or_404(db, exam_id)
    if exam.state != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam is not open",
        )

    result = await db.execute(
        select(StudentSession).where(
            StudentSession.exam_id == exam_id,
            StudentSession.student_id == student_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None or session.consent_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Consent required before accessing exam questions",
        )

    q_result = await db.execute(
        select(Question)
        .where(Question.quiz_id == exam.quiz_id)
        .order_by(Question.position)
    )
    return list(q_result.scalars().all())


# ---------------------------------------------------------------------------
# Grade report — professor view of all student answers
# ---------------------------------------------------------------------------


@router.get("/{exam_id}/grade", response_model=ExamGradeReport)
async def get_exam_grade(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> ExamGradeReport:
    """Return per-student answers with MCQ auto-scoring for a closed exam.

    Only the exam owner (professor) can access this endpoint.
    """
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)

    quiz_result = await db.execute(select(Quiz).where(Quiz.id == exam.quiz_id))
    quiz = quiz_result.scalar_one_or_none()
    quiz_title = quiz.title if quiz else "Unknown Quiz"

    # Load all questions ordered by position
    q_result = await db.execute(
        select(Question)
        .where(Question.quiz_id == exam.quiz_id)
        .order_by(Question.position)
    )
    questions = list(q_result.scalars().all())
    # question_map reserved for future use

    mcq_total = sum(1 for q in questions if q.type == "mcq")
    short_total = sum(1 for q in questions if q.type == "short")

    # Load all enrollments
    enrollment_result = await db.execute(
        select(Enrollment).where(Enrollment.exam_id == exam_id)
    )
    enrollments = list(enrollment_result.scalars().all())

    # Load user metadata for enrolled students
    student_ids = [e.student_id for e in enrollments]
    user_map: dict[str, User] = {}
    if student_ids:
        user_result = await db.execute(
            select(User).where(User.id.in_([uuid.UUID(sid) for sid in student_ids]))
        )
        for u in user_result.scalars().all():
            user_map[str(u.id)] = u

    # Load all answers for this exam
    answer_result = await db.execute(
        select(ExamAnswer).where(ExamAnswer.exam_id == exam_id)
    )
    all_answers = list(answer_result.scalars().all())

    # Group answers by student
    answers_by_student: dict[str, dict[str, ExamAnswer]] = {}
    for ans in all_answers:
        answers_by_student.setdefault(ans.student_id, {})[str(ans.question_id)] = ans

    student_entries: list[StudentGradeEntry] = []
    for enrollment in enrollments:
        sid = enrollment.student_id
        student_answers = answers_by_student.get(sid, {})
        user = user_map.get(sid)

        grade_answers: list[GradeAnswerItem] = []
        mcq_correct = 0

        for q in questions:
            qid = str(q.id)
            answer_row = student_answers.get(qid)
            student_answer = answer_row.answer if answer_row else ""

            if q.type == "mcq":
                is_correct = (
                    student_answer == q.correct_answer if student_answer else False
                )
                if is_correct:
                    mcq_correct += 1
            else:
                is_correct = None

            grade_answers.append(
                GradeAnswerItem(
                    question_id=q.id,
                    position=q.position,
                    question_type=cast(Literal["mcq", "short"], q.type),
                    prompt=q.prompt,
                    student_answer=student_answer,
                    correct_answer=q.correct_answer if q.type == "mcq" else None,
                    is_correct=is_correct,
                )
            )

        student_entries.append(
            StudentGradeEntry(
                student_id=sid,
                student_email=user.email if user else None,
                student_name=user.full_name if user else None,
                mcq_correct=mcq_correct,
                mcq_total=mcq_total,
                answers=grade_answers,
            )
        )

    return ExamGradeReport(
        exam_id=exam_id,
        quiz_title=quiz_title,
        course_id=exam.course_id,
        mcq_total=mcq_total,
        short_total=short_total,
        students=student_entries,
    )


# ---------------------------------------------------------------------------
# CSV Export (AEGIS-61)
# ---------------------------------------------------------------------------


@router.get("/{exam_id}/export")
async def export_session_csv(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> StreamingResponse:
    """Stream a UTF-8 CSV with per-student risk scores for a closed exam."""
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)

    if exam.state != "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam must be closed before exporting",
        )

    scores_result = await db.execute(
        select(SessionScore).where(SessionScore.exam_id == exam_id)
    )
    scores = scores_result.scalars().all()

    student_ids = [s.student_id for s in scores]
    name_map: dict[str, str] = {}
    if student_ids:
        valid_uuids = []
        for sid in student_ids:
            try:
                valid_uuids.append(uuid.UUID(sid))
            except ValueError:
                pass
        if valid_uuids:
            users_result = await db.execute(
                select(User).where(User.id.in_(valid_uuids))
            )
            for u in users_result.scalars().all():
                name_map[str(u.id)] = u.full_name or u.email

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "student_id",
            "student_name",
            "integrity_score",
            "tab_switch_score",
            "paste_score",
            "keystroke_score",
            "focus_loss_score",
            "answer_timing_score",
            "copy_sequence_score",
            "flagged",
        ]
    )
    for s in sorted(scores, key=lambda x: x.integrity_score, reverse=True):
        writer.writerow(
            [
                s.student_id,
                name_map.get(s.student_id, "Unknown"),
                round(s.integrity_score, 4),
                round(s.tab_switch_score, 4),
                round(s.paste_score, 4),
                round(s.keystroke_score, 4),
                round(s.focus_loss_score, 4),
                round(s.answer_timing_score, 4),
                round(s.copy_sequence_score, 4),
                "YES" if s.integrity_score >= 0.70 else "no",
            ]
        )

    output.seek(0)
    filename = f"aegis_session_{exam_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


async def _get_quiz_title(db: AsyncSession, quiz_id: uuid.UUID) -> str | None:
    result = await db.execute(select(Quiz.title).where(Quiz.id == quiz_id))
    return result.scalar_one_or_none()


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
