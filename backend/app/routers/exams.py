import csv
import io
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from typing import Literal, cast

from app.models.exam import Enrollment, ExamAnswer, ExamSession, StudentSession
from app.models.group import GroupMember, StudentGroup
from app.models.quiz import Question, Quiz
from app.models.telemetry import SessionScore
from app.models.user import User
from app.services.audit import (
    EXAM_CLOSED,
    EXAM_CREATED,
    EXAM_OPENED,
    record_audit_event,
)
from app.schemas.groups import EnrollGroup
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
    ManualGradeSubmit,
    QuestionForStudent,
    StudentGradeEntry,
    StudentSessionRead,
)
from app.services.exam_scheduling import auto_close_if_expired, auto_open_if_due
from app.services.scoring import dispatch_score_job

logger = logging.getLogger(__name__)

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
    await db.flush()
    record_audit_event(
        db,
        EXAM_CREATED,
        actor_id=user_id,
        target_id=str(exam.id),
        metadata={"course_id": exam.course_id},
    )
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

    # AEGIS-112b: which quizzes have short-answer questions? Needed so the
    # closed-exam action button reads "Evaluate" (grading still needed) vs
    # "View Grades" (MCQ-only, or already released) — mirrors student.py.
    quiz_ids = list({exam.quiz_id for exam, _ in rows})
    quizzes_with_short: set[uuid.UUID] = set()
    if quiz_ids:
        short_rows = await db.execute(
            select(Question.quiz_id)
            .where(Question.quiz_id.in_(quiz_ids), Question.type == "short")
            .distinct()
        )
        quizzes_with_short = {qid for (qid,) in short_rows.all()}

    items: list[ExamRead] = []
    for exam, quiz in rows:
        count = await _enrollment_count(db, exam.id)
        item = ExamRead.from_orm_with_count(exam, count, quiz_title=quiz.title)
        item.has_short_answers = exam.quiz_id in quizzes_with_short
        items.append(item)
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
    status_code=status.HTTP_201_CREATED,
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
    status_code=status.HTTP_201_CREATED,
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


@router.post("/{exam_id}/enroll-group", status_code=status.HTTP_201_CREATED)
async def enroll_group(
    exam_id: uuid.UUID,
    body: EnrollGroup,
    db: AsyncSession = Depends(get_db),
    professor_id: str = Depends(require_role("professor")),
) -> dict:
    """Enroll every current member of a group, skipping already-enrolled students."""
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, professor_id)
    if exam.state != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Students can only be enrolled while the exam is in draft state",
        )
    group = (
        await db.execute(select(StudentGroup).where(StudentGroup.id == body.group_id))
    ).scalar_one_or_none()
    if group is None or group.professor_id != professor_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    member_ids = (
        (
            await db.execute(
                select(GroupMember.student_id).where(
                    GroupMember.group_id == body.group_id
                )
            )
        )
        .scalars()
        .all()
    )
    existing = set(
        (
            await db.execute(
                select(Enrollment.student_id).where(Enrollment.exam_id == exam.id)
            )
        )
        .scalars()
        .all()
    )
    new_ids = [sid for sid in member_ids if sid not in existing]
    skipped_ids = [sid for sid in member_ids if sid in existing]
    for sid in new_ids:
        db.add(Enrollment(exam_id=exam.id, student_id=sid))
    await db.commit()

    # AEGIS-119: tell the professor which members were skipped because they were
    # already enrolled — by name/email, not just a count.
    skipped: list[str] = []
    if skipped_ids:
        valid = []
        for sid in skipped_ids:
            try:
                valid.append(uuid.UUID(sid))
            except (ValueError, TypeError):
                continue
        name_map: dict[str, str] = {}
        if valid:
            rows = await db.execute(select(User).where(User.id.in_(valid)))
            name_map = {
                str(u.id): (u.full_name or u.email) for u in rows.scalars().all()
            }
        skipped = [name_map.get(sid, sid) for sid in skipped_ids]

    return {
        "enrolled": len(new_ids),
        "group_size": len(member_ids),
        "skipped": skipped,
    }


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
    record_audit_event(db, EXAM_OPENED, actor_id=user_id, target_id=str(exam.id))
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
    record_audit_event(db, EXAM_CLOSED, actor_id=user_id, target_id=str(exam.id))
    await db.commit()
    await db.refresh(exam)

    # Notify every connected student that the exam closed and end their sessions
    # simultaneously (AEGIS-104). Late import avoids a module-level cycle; a WS
    # failure must never break exam closure.
    try:
        from app.routers.telemetry import close_exam_sessions

        notified = await close_exam_sessions(str(exam.id))
        logger.info("Exam %s closed — notified %d student(s)", exam.id, notified)
    except Exception:
        logger.exception("Failed to notify students of exam %s closure", exam.id)

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

    # AEGIS-111: once the exam is finished, it's final — no re-entry or edits.
    session_result = await db.execute(
        select(StudentSession).where(
            StudentSession.exam_id == exam_id,
            StudentSession.student_id == student_id,
        )
    )
    session = session_result.scalar_one_or_none()
    if session is not None and session.submitted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This exam has already been submitted and can no longer be changed.",
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

    # AEGIS-111: finalise the exam on the "Finish Exam" submit so it can't be
    # re-entered. Create the session row if it doesn't exist yet (defensive).
    if body.final:
        if session is None:
            session = StudentSession(exam_id=exam_id, student_id=student_id)
            db.add(session)
        session.submitted_at = now

    # Commit DB writes unconditionally — this is the durable store.
    await db.commit()

    for answer in saved:
        await db.refresh(answer)

    answer_reads = [AnswerItemRead.model_validate(a) for a in saved]
    return AnswerSubmitResponse(
        saved=len(saved),
        answers=answer_reads,
        submitted_at=session.submitted_at if session else None,
    )


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
    exam = await _get_exam_or_404(db, exam_id)
    # Open the exam if its scheduled start has passed (AEGIS-104 auto-open).
    await auto_open_if_due(db, exam)
    await auto_close_if_expired(db, exam)

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

    read = StudentSessionRead.model_validate(session)
    read.exam_state = exam.state
    read.mode = exam.mode
    return read


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
    exam = await _get_exam_or_404(db, exam_id)
    read = StudentSessionRead.model_validate(session)
    read.exam_state = exam.state
    read.mode = exam.mode
    return read


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
    # Open on demand if the scheduled start has passed (AEGIS-104 auto-open).
    await auto_open_if_due(db, exam)
    await auto_close_if_expired(db, exam)
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
    # AEGIS-111: a finished exam can't be re-opened.
    if session.submitted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This exam has already been submitted.",
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

    # AEGIS-118: a StudentSession row (or a saved answer) means the student
    # actually engaged with the exam — distinguishes "Absent" (neither) from
    # "attended but left answers blank".
    session_result = await db.execute(
        select(StudentSession.student_id).where(StudentSession.exam_id == exam_id)
    )
    attended_ids = {row[0] for row in session_result.all()}
    attended_ids |= {ans.student_id for ans in all_answers}

    # AEGIS-119: per-student integrity score, for auto-highlighting high-risk
    # ("copy") students in the grade view.
    score_result = await db.execute(
        select(SessionScore.student_id, SessionScore.integrity_score).where(
            SessionScore.exam_id == exam_id
        )
    )
    integrity_by_student = {sid: score for sid, score in score_result.all()}

    # Group answers by student
    answers_by_student: dict[str, dict[str, ExamAnswer]] = {}
    for ans in all_answers:
        answers_by_student.setdefault(ans.student_id, {})[str(ans.question_id)] = ans

    student_entries: list[StudentGradeEntry] = []
    ungraded_short = 0  # AEGIS-112b: submitted short answers still lacking a score
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
                if answer_row is not None and answer_row.manual_score is None:
                    ungraded_short += 1

            grade_answers.append(
                GradeAnswerItem(
                    question_id=q.id,
                    answer_id=answer_row.id if answer_row else None,
                    position=q.position,
                    question_type=cast(Literal["mcq", "short"], q.type),
                    prompt=q.prompt,
                    student_answer=student_answer,
                    correct_answer=q.correct_answer if q.type == "mcq" else None,
                    is_correct=is_correct,
                    manual_score=answer_row.manual_score if answer_row else None,
                    max_score=q.max_score,
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
                attended=sid in attended_ids,
                integrity_score=integrity_by_student.get(sid),
            )
        )

    return ExamGradeReport(
        exam_id=exam_id,
        quiz_title=quiz_title,
        course_id=exam.course_id,
        mcq_total=mcq_total,
        short_total=short_total,
        students=student_entries,
        results_released=exam.results_released_at is not None,
        ungraded_short=ungraded_short,
        mode=exam.mode,
    )


@router.post("/{exam_id}/release-results", response_model=ExamGradeReport)
async def release_results(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> ExamGradeReport:
    """AEGIS-112b: release results to students ("Submit Grades").

    Only the owner, on a closed exam, and only once every gradable answer has
    a score — blocks premature release with an actionable ungraded count.
    Idempotent — releasing again just returns the current report (so
    re-editing a grade and re-releasing is safe).
    Returns the refreshed grade report.
    """
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)
    if exam.state != "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Results can only be released for a closed exam",
        )
    if exam.results_released_at is None:
        report = await get_exam_grade(exam_id, db=db, user_id=user_id)
        if report.ungraded_short > 0:
            plural = report.ungraded_short != 1
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"{report.ungraded_short} answer{'s' if plural else ''} "
                    f"still {'need' if plural else 'needs'} grading before "
                    "results can be released."
                ),
            )
        exam.results_released_at = datetime.now(timezone.utc)
        await db.commit()
        report.results_released = True
        return report
    return await get_exam_grade(exam_id, db=db, user_id=user_id)


@router.patch("/{exam_id}/answers/grade", status_code=status.HTTP_200_OK)
async def submit_manual_grade(
    exam_id: uuid.UUID,
    body: ManualGradeSubmit,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> dict:
    """Set a manual score on a short-answer ExamAnswer row.

    Only the exam owner can grade; only works on closed exams; only applies to short-answer questions (MCQ scores are computed automatically).
    """
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)

    if exam.state != "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Grades can only be submitted for closed exams",
        )

    answer_result = await db.execute(
        select(ExamAnswer).where(
            ExamAnswer.id == body.answer_id,
            ExamAnswer.exam_id == exam_id,
        )
    )
    answer = answer_result.scalar_one_or_none()
    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer not found",
        )

    # validate score against question max_score
    q_result = await db.execute(
        select(Question).where(Question.id == answer.question_id)
    )
    question = q_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
    if question.type != "short":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual grading only applies to short-answer questions",
        )
    if body.score < 0 or body.score > question.max_score:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Score must be between 0 and {question.max_score}",
        )

    answer.manual_score = body.score
    await db.commit()
    return {"answer_id": str(body.answer_id), "manual_score": body.score}


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

    # AEGIS-118: enrolled students with zero telemetry get no SessionScore row
    # in the old flow — iterate enrollments (not scores) so nobody is silently
    # omitted from the export.
    enrollment_result = await db.execute(
        select(Enrollment.student_id).where(Enrollment.exam_id == exam_id)
    )
    enrolled_ids = [row[0] for row in enrollment_result.all()]

    scores_result = await db.execute(
        select(SessionScore).where(SessionScore.exam_id == exam_id)
    )
    scores_by_student = {s.student_id: s for s in scores_result.scalars().all()}

    student_ids = list(set(enrolled_ids) | set(scores_by_student.keys()))
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
            "has_telemetry",
        ]
    )

    def _sort_key(sid: str) -> float:
        s = scores_by_student.get(sid)
        return s.integrity_score if s else 0.0

    for sid in sorted(student_ids, key=_sort_key, reverse=True):
        s = scores_by_student.get(sid)
        writer.writerow(
            [
                sid,
                name_map.get(sid, "Unknown"),
                round(s.integrity_score, 4) if s else 0.0,
                round(s.tab_switch_score, 4) if s else 0.0,
                round(s.paste_score, 4) if s else 0.0,
                round(s.keystroke_score, 4) if s else 0.0,
                round(s.focus_loss_score, 4) if s else 0.0,
                round(s.answer_timing_score, 4) if s else 0.0,
                round(s.copy_sequence_score, 4) if s else 0.0,
                "YES" if s and s.integrity_score >= 0.70 else "no",
                "YES" if s and s.has_telemetry else "NO",
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
