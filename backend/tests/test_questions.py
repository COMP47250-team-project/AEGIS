"""Tests for GET /exams/{exam_id}/questions endpoint (AEGIS-39).

The endpoint:
- Requires an open exam (409 otherwise)
- Requires a consented student session (403 otherwise)
- Returns questions ordered by position
- Never exposes correct_answer
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.main import app

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

QUIZ_PAYLOAD = {
    "title": "Questions Test Quiz",
    "description": "Quiz for AEGIS-39 tests.",
    "duration_minutes": 45,
}

MCQ_QUESTION = {
    "type": "mcq",
    "prompt": "Which layer of the OSI model is responsible for routing?",
    "options": ["Network", "Transport", "Data Link", "Session"],
    "correct_answer": "Network",
    "position": 0,
}

SHORT_QUESTION = {
    "type": "short",
    "prompt": "Explain the difference between TCP and UDP.",
    "position": 1,
}

EXAM_PAYLOAD = {
    "course_id": "CS201",
    "scheduled_start": "2026-09-01T09:00:00+00:00",
    "duration_minutes": 60,
}

STUDENT_ID = "student-questions-1"


def _student_client(student_id: str = STUDENT_ID) -> AsyncClient:
    token = jwt.encode(
        {"sub": student_id}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _setup_open_exam_with_questions(client: AsyncClient) -> tuple[str, str, str]:
    """Create quiz with MCQ + short questions, exam, enroll student, open.

    Returns (exam_id, mcq_question_id, short_question_id).
    """
    quiz_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    assert quiz_resp.status_code == 201
    quiz_id = quiz_resp.json()["id"]

    mcq_resp = await client.post(f"/quizzes/{quiz_id}/questions", json=MCQ_QUESTION)
    assert mcq_resp.status_code == 201
    mcq_id = mcq_resp.json()["id"]

    short_resp = await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_QUESTION)
    assert short_resp.status_code == 201
    short_id = short_resp.json()["id"]

    exam_resp = await client.post("/exams", json={**EXAM_PAYLOAD, "quiz_id": quiz_id})
    assert exam_resp.status_code == 201
    exam_id = exam_resp.json()["id"]

    enroll_resp = await client.post(
        f"/exams/{exam_id}/enrollments", json={"student_id": STUDENT_ID}
    )
    assert enroll_resp.status_code == 201

    open_resp = await client.post(f"/exams/{exam_id}/open")
    assert open_resp.status_code == 200

    return exam_id, mcq_id, short_id


async def _consent(exam_id: str) -> None:
    async with _student_client() as student:
        resp = await student.post(f"/exams/{exam_id}/consent")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_questions_returned_for_consented_student(client: AsyncClient) -> None:
    exam_id, _, _ = await _setup_open_exam_with_questions(client)
    await _consent(exam_id)

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/questions")

    assert resp.status_code == 200
    questions = resp.json()
    assert len(questions) == 2


@pytest.mark.asyncio
async def test_questions_contain_expected_fields(client: AsyncClient) -> None:
    exam_id, mcq_id, short_id = await _setup_open_exam_with_questions(client)
    await _consent(exam_id)

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/questions")

    questions = resp.json()
    ids = {q["id"] for q in questions}
    assert mcq_id in ids
    assert short_id in ids

    for q in questions:
        assert "id" in q
        assert "type" in q
        assert "prompt" in q
        assert "position" in q
        assert "options" in q


@pytest.mark.asyncio
async def test_correct_answer_not_exposed(client: AsyncClient) -> None:
    exam_id, _, _ = await _setup_open_exam_with_questions(client)
    await _consent(exam_id)

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/questions")

    for q in resp.json():
        assert "correct_answer" not in q


@pytest.mark.asyncio
async def test_mcq_question_has_options(client: AsyncClient) -> None:
    exam_id, mcq_id, _ = await _setup_open_exam_with_questions(client)
    await _consent(exam_id)

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/questions")

    mcq = next(q for q in resp.json() if q["id"] == mcq_id)
    assert mcq["type"] == "mcq"
    assert isinstance(mcq["options"], list)
    assert len(mcq["options"]) == 4


@pytest.mark.asyncio
async def test_short_question_has_null_options(client: AsyncClient) -> None:
    exam_id, _, short_id = await _setup_open_exam_with_questions(client)
    await _consent(exam_id)

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/questions")

    short = next(q for q in resp.json() if q["id"] == short_id)
    assert short["type"] == "short"
    assert short["options"] is None


@pytest.mark.asyncio
async def test_questions_ordered_by_position(client: AsyncClient) -> None:
    exam_id, _, _ = await _setup_open_exam_with_questions(client)
    await _consent(exam_id)

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/questions")

    positions = [q["position"] for q in resp.json()]
    assert positions == sorted(positions)


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_questions_rejected_when_exam_is_draft(client: AsyncClient) -> None:
    quiz_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = quiz_resp.json()["id"]
    await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_QUESTION)
    exam_resp = await client.post("/exams", json={**EXAM_PAYLOAD, "quiz_id": quiz_id})
    exam_id = exam_resp.json()["id"]

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/questions")

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_questions_rejected_without_consent(client: AsyncClient) -> None:
    exam_id, _, _ = await _setup_open_exam_with_questions(client)
    # No consent recorded — session is created but consent_at is None

    async with _student_client() as student:
        # Create the session (no consent)
        await student.get(f"/exams/{exam_id}/session")
        resp = await student.get(f"/exams/{exam_id}/questions")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_questions_rejected_with_no_session(client: AsyncClient) -> None:
    exam_id, _, _ = await _setup_open_exam_with_questions(client)
    # Different student has no session and no consent

    other_student = "student-no-session-99"
    async with _student_client(other_student) as student:
        resp = await student.get(f"/exams/{exam_id}/questions")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_questions_unauthenticated_returns_401_or_403(client: AsyncClient) -> None:
    exam_id, _, _ = await _setup_open_exam_with_questions(client)
    await _consent(exam_id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as unauthed:
        resp = await unauthed.get(f"/exams/{exam_id}/questions")

    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_questions_nonexistent_exam_returns_404(client: AsyncClient) -> None:
    async with _student_client() as student:
        resp = await student.get(f"/exams/{uuid.uuid4()}/questions")

    assert resp.status_code == 404
