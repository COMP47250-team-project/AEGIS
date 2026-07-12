import uuid
from datetime import timedelta
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.exam import Enrollment, ExamAnswer, ExamSession, StudentSession
from app.models.quiz import Question, Quiz
from app.models.telemetry import SessionScore
from app.services.exam_scheduling import auto_open_due
from app.schemas.exam import (
    StudentAnswerResult,
    StudentExamListItem,
    StudentExamResults,
)

router = APIRouter(prefix="/student", tags=["student"])


@router.get("/sessions", response_model=list[StudentExamListItem])
async def list_student_sessions(
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(require_role("student")),
) -> list[StudentExamListItem]:
    """Return all exam sessions the authenticated student is enrolled in."""
    result = await db.execute(
        select(ExamSession, Quiz, StudentSession)
        .join(Quiz, ExamSession.quiz_id == Quiz.id)
        .join(Enrollment, Enrollment.exam_id == ExamSession.id)
        .outerjoin(
            StudentSession,
            (StudentSession.exam_id == ExamSession.id)
            & (StudentSession.student_id == student_id),
        )
        .where(Enrollment.student_id == student_id)
        .order_by(ExamSession.scheduled_start.desc())
    )
    rows = result.all()

    # Auto-open any exam whose scheduled start has passed so a waiting student
    # sees it as open without the professor manually triggering it (AEGIS-104).
    await auto_open_due(db, [exam for exam, _, _ in rows])

    items: list[StudentExamListItem] = []
    for exam, quiz, session in rows:
        submitted = session is not None and session.submitted_at is not None
        if exam.state == "closed":
            status_val = "completed"
            effective_start = exam.opened_at or exam.scheduled_start
        elif submitted:
            # AEGIS-111: student finished — show "submitted" (no re-entry),
            # even while the exam is still open for others.
            status_val = "submitted"
            effective_start = exam.opened_at or exam.scheduled_start
        elif exam.state == "open":
            status_val = "open"
            effective_start = exam.opened_at or exam.scheduled_start
        else:
            status_val = "upcoming"
            effective_start = exam.scheduled_start

        ends_at = effective_start + timedelta(minutes=exam.duration_minutes)

        items.append(
            StudentExamListItem(
                exam_id=exam.id,
                exam_title=quiz.title,
                course_name=exam.course_id,
                status=status_val,
                starts_at=exam.scheduled_start,
                ends_at=ends_at,
            )
        )

    return items


@router.get("/exams/{exam_id}/results", response_model=StudentExamResults)
async def get_student_exam_results(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(require_role("student")),
) -> StudentExamResults:
    """Return a student's own results for a completed exam.

    Reveals correct answers for MCQ questions. Only available once the exam
    is closed so students cannot use this to cheat during the exam.
    """
    exam_result = await db.execute(select(ExamSession).where(ExamSession.id == exam_id))
    exam = exam_result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found"
        )

    if exam.state != "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Results are only available after the exam is closed",
        )

    # Verify the student was enrolled
    enrollment_result = await db.execute(
        select(Enrollment).where(
            Enrollment.exam_id == exam_id,
            Enrollment.student_id == student_id,
        )
    )
    if enrollment_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this exam",
        )

    # Load quiz details
    quiz_result = await db.execute(select(Quiz).where(Quiz.id == exam.quiz_id))
    quiz = quiz_result.scalar_one_or_none()

    # Load questions ordered by position
    q_result = await db.execute(
        select(Question)
        .where(Question.quiz_id == exam.quiz_id)
        .order_by(Question.position)
    )
    questions = list(q_result.scalars().all())

    # Load this student's answers
    answer_result = await db.execute(
        select(ExamAnswer).where(
            ExamAnswer.exam_id == exam_id,
            ExamAnswer.student_id == student_id,
        )
    )
    answers_by_qid = {str(a.question_id): a for a in answer_result.scalars().all()}

    answer_results: list[StudentAnswerResult] = []
    mcq_correct = 0
    mcq_total = 0
    points_earned = 0.0
    points_possible = 0
    fully_graded = True

    for q in questions:
        qid = str(q.id)
        ans = answers_by_qid.get(qid)
        student_answer = ans.answer if ans else ""

        manual_score = ans.manual_score if ans else None
        # AEGIS-112: build the overall points total (MCQ + manual short answers).
        points_possible += q.max_score

        if q.type == "mcq":
            mcq_total += 1
            is_correct = student_answer == q.correct_answer if student_answer else False
            if is_correct:
                mcq_correct += 1
                points_earned += q.max_score
            correct_answer = q.correct_answer
        else:
            is_correct = None
            correct_answer = None
            if manual_score is not None:
                points_earned += manual_score
            else:
                fully_graded = False  # a short answer still needs grading

        answer_results.append(
            StudentAnswerResult(
                question_id=q.id,
                position=q.position,
                question_type=cast(Literal["mcq", "short"], q.type),
                prompt=q.prompt,
                options=q.options,
                student_answer=student_answer,
                correct_answer=correct_answer,
                is_correct=is_correct,
                manual_score=manual_score,
                max_score=q.max_score,
            )
        )

    # Fetch the integrity score computed by the async scoring service.
    score_result = await db.execute(
        select(SessionScore).where(
            SessionScore.exam_id == exam_id,
            SessionScore.student_id == student_id,
        )
    )
    session_score = score_result.scalar_one_or_none()
    integrity_score = session_score.integrity_score if session_score else None

    return StudentExamResults(
        exam_id=exam_id,
        exam_title=quiz.title if quiz else "Unknown Quiz",
        course_name=exam.course_id,
        closed_at=exam.closed_at,
        mcq_correct=mcq_correct,
        mcq_total=mcq_total,
        questions=answer_results,
        integrity_score=integrity_score,
        points_earned=points_earned,
        points_possible=points_possible,
        fully_graded=fully_graded,
    )
