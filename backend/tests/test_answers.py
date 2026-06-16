"""Tests for answer submission endpoint (AEGIS-35).

Critical invariant: POST /exams/{exam_id}/answers must persist answers to
PostgreSQL and return 200 regardless of WebSocket or Service Bus availability.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

QUIZ_PAYLOAD = {
    "title": "Answer Test Quiz",
    "description": "Quiz for AEGIS-35 tests.",
    "duration_minutes": 30,
}

SHORT_QUESTION = {
    "type": "short",
    "prompt": "Explain TCP/IP.",
}

MCQ_QUESTION = {
    "type": "mcq",
    "prompt": "Which layer is IP?",
    "options": ["Application", "Transport", "Network", "Data Link"],
    "correct_answer": "Network",
}

EXAM_PAYLOAD = {
    "course_id": "CS101",
    "scheduled_start": "2026-09-01T09:00:00+00:00",
    "duration_minutes": 60,
}

STUDENT_ID = "student-100"


def _student_client() -> AsyncClient:
    token = jwt.encode(
        {"sub": STUDENT_ID}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _setup_open_exam(client: AsyncClient) -> tuple[str, str, str]:
    """Create quiz with two questions, create exam, enroll student, open.

    Returns (exam_id, short_question_id, mcq_question_id).
    """
    quiz_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    assert quiz_resp.status_code == 201
    quiz_id = quiz_resp.json()["id"]

    short_resp = await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_QUESTION)
    assert short_resp.status_code == 201
    short_q_id = short_resp.json()["id"]

    mcq_resp = await client.post(f"/quizzes/{quiz_id}/questions", json=MCQ_QUESTION)
    assert mcq_resp.status_code == 201
    mcq_q_id = mcq_resp.json()["id"]

    exam_resp = await client.post("/exams", json={**EXAM_PAYLOAD, "quiz_id": quiz_id})
    assert exam_resp.status_code == 201
    exam_id = exam_resp.json()["id"]

    enroll_resp = await client.post(
        f"/exams/{exam_id}/enrollments", json={"student_id": STUDENT_ID}
    )
    assert enroll_resp.status_code == 201

    open_resp = await client.post(f"/exams/{exam_id}/open")
    assert open_resp.status_code == 200

    return exam_id, short_q_id, mcq_q_id


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_answers_returns_200(client: AsyncClient) -> None:
    exam_id, short_q_id, mcq_q_id = await _setup_open_exam(client)

    async with _student_client() as student:
        resp = await student.post(
            f"/exams/{exam_id}/answers",
            json={
                "answers": [
                    {
                        "question_id": short_q_id,
                        "answer": "TCP/IP is a networking protocol suite.",
                    },
                    {"question_id": mcq_q_id, "answer": "Network"},
                ]
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] == 2
    assert len(data["answers"]) == 2


@pytest.mark.asyncio
async def test_submit_answers_durable_in_db(client: AsyncClient) -> None:
    """Answers committed to DB are returned with their persisted content."""
    exam_id, short_q_id, _ = await _setup_open_exam(client)

    async with _student_client() as student:
        resp = await student.post(
            f"/exams/{exam_id}/answers",
            json={"answers": [{"question_id": short_q_id, "answer": "Durable answer"}]},
        )
    assert resp.status_code == 200

    answer = resp.json()["answers"][0]
    assert answer["exam_id"] == exam_id
    assert answer["student_id"] == STUDENT_ID
    assert answer["question_id"] == short_q_id
    assert answer["answer"] == "Durable answer"
    assert "saved_at" in answer


# ---------------------------------------------------------------------------
# Partial save / upsert (auto-save every 30s)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_save_upserts_existing_answer(client: AsyncClient) -> None:
    """Submitting the same question twice updates the answer (upsert)."""
    exam_id, short_q_id, _ = await _setup_open_exam(client)

    async with _student_client() as student:
        first = await student.post(
            f"/exams/{exam_id}/answers",
            json={"answers": [{"question_id": short_q_id, "answer": "Draft answer"}]},
        )
        assert first.status_code == 200

        second = await student.post(
            f"/exams/{exam_id}/answers",
            json={
                "answers": [
                    {"question_id": short_q_id, "answer": "Updated final answer"}
                ]
            },
        )
        assert second.status_code == 200

    data = second.json()
    assert data["saved"] == 1
    assert data["answers"][0]["answer"] == "Updated final answer"


@pytest.mark.asyncio
async def test_partial_save_subset_of_questions(client: AsyncClient) -> None:
    """Can submit answers for only a subset of questions (partial save)."""
    exam_id, short_q_id, mcq_q_id = await _setup_open_exam(client)

    async with _student_client() as student:
        # Submit only the short answer question, not the MCQ
        resp = await student.post(
            f"/exams/{exam_id}/answers",
            json={"answers": [{"question_id": short_q_id, "answer": "Partial"}]},
        )

    assert resp.status_code == 200
    assert resp.json()["saved"] == 1


# ---------------------------------------------------------------------------
# Resilience — WebSocket / Service Bus unavailability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_answers_persisted_independent_of_side_effects(
    client: AsyncClient,
) -> None:
    """Answers are stored even when no external services are available.

    The endpoint must not call WebSocket or Service Bus directly.
    This test verifies the endpoint succeeds without any external
    infrastructure configured (which matches the test environment).
    """
    exam_id, short_q_id, _ = await _setup_open_exam(client)

    async with _student_client() as student:
        resp = await student.post(
            f"/exams/{exam_id}/answers",
            json={
                "answers": [{"question_id": short_q_id, "answer": "Resilient answer"}]
            },
        )

    # Must return 200 regardless of Service Bus / WebSocket availability
    assert resp.status_code == 200
    assert resp.json()["saved"] == 1


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_answers_to_draft_exam_returns_409(client: AsyncClient) -> None:
    quiz_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = quiz_resp.json()["id"]
    short_resp = await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_QUESTION)
    q_id = short_resp.json()["id"]

    exam_resp = await client.post("/exams", json={**EXAM_PAYLOAD, "quiz_id": quiz_id})
    exam_id = exam_resp.json()["id"]

    async with _student_client() as student:
        resp = await student.post(
            f"/exams/{exam_id}/answers",
            json={"answers": [{"question_id": q_id, "answer": "Too early"}]},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_submit_answers_to_closed_exam_returns_409(client: AsyncClient) -> None:
    exam_id, short_q_id, _ = await _setup_open_exam(client)
    await client.post(f"/exams/{exam_id}/close")

    async with _student_client() as student:
        resp = await student.post(
            f"/exams/{exam_id}/answers",
            json={"answers": [{"question_id": short_q_id, "answer": "Too late"}]},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_submit_answers_to_nonexistent_exam_returns_404(
    client: AsyncClient,
) -> None:
    import uuid

    fake_exam_id = str(uuid.uuid4())
    fake_q_id = str(uuid.uuid4())

    async with _student_client() as student:
        resp = await student.post(
            f"/exams/{fake_exam_id}/answers",
            json={"answers": [{"question_id": fake_q_id, "answer": "Ghost"}]},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_empty_answers_list_returns_422(client: AsyncClient) -> None:
    exam_id, _, _ = await _setup_open_exam(client)

    async with _student_client() as student:
        resp = await student.post(
            f"/exams/{exam_id}/answers",
            json={"answers": []},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_answers_unauthenticated_returns_401_or_403() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as unauthed:
        import uuid

        resp = await unauthed.post(
            f"/exams/{uuid.uuid4()}/answers",
            json={"answers": [{"question_id": str(uuid.uuid4()), "answer": "x"}]},
        )

    assert resp.status_code in (401, 403)
