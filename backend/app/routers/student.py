import uuid
from datetime import timedelta
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.exam import Enrollment, ExamAnswer, ExamSession
from app.models.quiz import Question, Quiz
from app.schemas.exam import (
    StudentAnswerResult,
    StudentExamListItem,
    StudentExamResults,
)

router = APIRouter(prefix="/student", tags=["student"])


@router.get("/sessions", response_model=list[StudentExamListItem])
async def list_student_sessions(
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(get_current_user_id),
) -> list[StudentExamListItem]:
    """Return all exam sessions the authenticated student is enrolled in."""
    result = await db.execute(
        select(ExamSession, Quiz)
        .join(Quiz, ExamSession.quiz_id == Quiz.id)
        .join(Enrollment, Enrollment.exam_id == ExamSession.id)
        .where(Enrollment.student_id == student_id)
        .order_by(ExamSession.scheduled_start.desc())
    )
    rows = result.all()

    items: list[StudentExamListItem] = []
    for exam, quiz in rows:
        if exam.state == "open":
            status_val = "open"
            effective_start = exam.opened_at or exam.scheduled_start
        elif exam.state == "closed":
            status_val = "completed"
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
    student_id: str = Depends(get_current_user_id),
) -> StudentExamResults:
    """Return a student's own results for a completed exam.

    Reveals correct answers for MCQ questions. Only available once the exam
    is closed so students cannot use this to cheat during the exam.
    """
    exam_result = await db.execute(
        select(ExamSession).where(ExamSession.id == exam_id)
    )
    exam = exam_result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

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

    for q in questions:
        qid = str(q.id)
        ans = answers_by_qid.get(qid)
        student_answer = ans.answer if ans else ""

        if q.type == "mcq":
            mcq_total += 1
            is_correct = student_answer == q.correct_answer if student_answer else False
            if is_correct:
                mcq_correct += 1
            correct_answer = q.correct_answer
        else:
            is_correct = None
            correct_answer = None

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
            )
        )

    return StudentExamResults(
        exam_id=exam_id,
        exam_title=quiz.title if quiz else "Unknown Quiz",
        course_name=exam.course_id,
        closed_at=exam.closed_at,
        mcq_correct=mcq_correct,
        mcq_total=mcq_total,
        questions=answer_results,
    )
