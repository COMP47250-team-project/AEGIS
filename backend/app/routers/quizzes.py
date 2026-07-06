import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user_id, require_role
from app.models.quiz import Question, Quiz
from app.schemas.quiz import (
    QuestionBankItem,
    QuestionBankResponse,
    QuestionCreate,
    QuestionRead,
    QuestionUpdate,
    QuizCreate,
    QuizRead,
)

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


# ---------------------------------------------------------------------------
# Quiz endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=QuizRead, status_code=status.HTTP_201_CREATED)
async def create_quiz(
    body: QuizCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Quiz:
    quiz = Quiz(**body.model_dump(), created_by=user_id)
    db.add(quiz)
    await db.commit()
    result = await db.execute(
        select(Quiz).where(Quiz.id == quiz.id).options(selectinload(Quiz.questions))
    )
    return result.scalar_one()


@router.get("", response_model=list[QuizRead])
async def list_quizzes(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[Quiz]:
    result = await db.execute(
        select(Quiz)
        .where(Quiz.created_by == user_id)
        .options(selectinload(Quiz.questions))
        .order_by(Quiz.created_at.desc())
    )
    return list(result.scalars().all())


# NOTE: this must be declared BEFORE `/{quiz_id}` so "question-bank" isn't
# captured as a quiz id.
@router.get("/question-bank", response_model=QuestionBankResponse)
async def question_bank(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
    search: str | None = Query(None, description="Filter by question text (prompt)."),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> QuestionBankResponse:
    """Paginated bank of every question across the professor's own quizzes, so
    they can reuse well-tested questions in a new quiz (AEGIS-90)."""
    base = (
        select(Question, Quiz.title, Quiz.created_at)
        .join(Quiz, Question.quiz_id == Quiz.id)
        .where(Quiz.created_by == user_id)
    )
    if search:
        base = base.where(Question.prompt.ilike(f"%{search}%"))

    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = (
        await db.execute(
            base.order_by(Quiz.created_at.desc(), Question.position)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        QuestionBankItem(
            question_id=q.id,
            quiz_id=q.quiz_id,
            quiz_title=quiz_title,
            question_text=q.prompt,
            question_type=q.type,
            options=q.options,
            correct_answer=q.correct_answer,
            created_at=created_at,
        )
        for (q, quiz_title, created_at) in rows
    ]
    return QuestionBankResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/{quiz_id}", response_model=QuizRead)
async def get_quiz(
    quiz_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> Quiz:
    result = await db.execute(
        select(Quiz).where(Quiz.id == quiz_id).options(selectinload(Quiz.questions))
    )
    quiz = result.scalar_one_or_none()
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )
    return quiz


# ---------------------------------------------------------------------------
# Question endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{quiz_id}/questions",
    response_model=QuestionRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_question(
    quiz_id: uuid.UUID,
    body: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> Question:
    quiz = await _get_quiz_or_404(db, quiz_id)

    if body.position is None:
        existing = await db.execute(select(Question).where(Question.quiz_id == quiz_id))
        next_position = len(existing.scalars().all())
    else:
        next_position = body.position

    question = Question(
        quiz_id=quiz.id,
        type=body.type,
        prompt=body.prompt,
        options=body.options,
        correct_answer=body.correct_answer,
        position=next_position,
        max_score=body.max_score,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question


@router.put("/{quiz_id}/questions/{question_id}", response_model=QuestionRead)
async def update_question(
    quiz_id: uuid.UUID,
    question_id: uuid.UUID,
    body: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> Question:
    await _get_quiz_or_404(db, quiz_id)
    question = await _get_question_or_404(db, quiz_id, question_id)

    patch = body.model_dump(exclude_unset=True)

    # Merge update fields, then validate MCQ rules with merged state
    new_type = patch.get("type", question.type)
    new_options = patch.get("options", question.options)

    if new_type == "mcq":
        if new_options is None or len(new_options) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="MCQ questions require at least 2 options",
            )
        new_correct = patch.get("correct_answer", question.correct_answer)
        if not new_correct:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="MCQ questions require a correct_answer",
            )

    for field, value in patch.items():
        setattr(question, field, value)

    await db.commit()
    await db.refresh(question)
    return question


@router.post("/{quiz_id}/publish", response_model=QuizRead)
async def publish_quiz(
    quiz_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> Quiz:
    quiz = await _get_quiz_or_404(db, quiz_id)

    if quiz.is_published:
        result = await db.execute(
            select(Quiz).where(Quiz.id == quiz_id).options(selectinload(Quiz.questions))
        )
        return result.scalar_one()

    result = await db.execute(select(Question).where(Question.quiz_id == quiz_id))
    if not result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A quiz must have at least 1 question before it can be published",
        )

    quiz.is_published = True
    await db.commit()

    result = await db.execute(
        select(Quiz).where(Quiz.id == quiz_id).options(selectinload(Quiz.questions))
    )
    return result.scalar_one()


@router.delete(
    "/{quiz_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_question(
    quiz_id: uuid.UUID,
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> None:
    await _get_quiz_or_404(db, quiz_id)
    question = await _get_question_or_404(db, quiz_id, question_id)
    await db.delete(question)
    await db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_quiz_or_404(db: AsyncSession, quiz_id: uuid.UUID) -> Quiz:
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )
    return quiz


async def _get_question_or_404(
    db: AsyncSession, quiz_id: uuid.UUID, question_id: uuid.UUID
) -> Question:
    result = await db.execute(
        select(Question).where(
            Question.id == question_id,
            Question.quiz_id == quiz_id,
        )
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not found"
        )
    return question
