"""Tests for quiz and question CRUD endpoints (AEGIS-33)."""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

QUIZ_PAYLOAD = {
    "title": "Python Fundamentals",
    "description": "A quiz on Python basics.",
    "duration_minutes": 20,
}

MCQ_PAYLOAD = {
    "type": "mcq",
    "prompt": "What keyword is used to define a function in Python?",
    "options": ["func", "def", "define", "lambda"],
    "correct_answer": "def",
}

SHORT_PAYLOAD = {
    "type": "short",
    "prompt": "Explain what a Python decorator does.",
}


# ---------------------------------------------------------------------------
# Quiz creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_quiz_returns_201(client: AsyncClient) -> None:
    response = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == QUIZ_PAYLOAD["title"]
    assert data["duration_minutes"] == QUIZ_PAYLOAD["duration_minutes"]
    assert data["is_published"] is False
    assert "id" in data
    assert data["questions"] == []


@pytest.mark.asyncio
async def test_create_quiz_missing_title_returns_422(client: AsyncClient) -> None:
    response = await client.post("/quizzes", json={"duration_minutes": 10})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_quiz_invalid_duration_returns_422(client: AsyncClient) -> None:
    response = await client.post("/quizzes", json={"title": "Q", "duration_minutes": 0})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Get quiz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_quiz_returns_quiz_with_questions(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]

    await client.post(f"/quizzes/{quiz_id}/questions", json=MCQ_PAYLOAD)
    await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_PAYLOAD)

    response = await client.get(f"/quizzes/{quiz_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == quiz_id
    assert len(data["questions"]) == 2


@pytest.mark.asyncio
async def test_get_quiz_not_found_returns_404(client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/quizzes/{fake_id}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Add MCQ question
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_mcq_question_returns_201(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]

    response = await client.post(f"/quizzes/{quiz_id}/questions", json=MCQ_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "mcq"
    assert data["prompt"] == MCQ_PAYLOAD["prompt"]
    assert data["options"] == MCQ_PAYLOAD["options"]
    assert data["correct_answer"] == MCQ_PAYLOAD["correct_answer"]


@pytest.mark.asyncio
async def test_add_mcq_missing_options_returns_422(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]

    bad_mcq = {"type": "mcq", "prompt": "What is 2+2?", "correct_answer": "4"}
    response = await client.post(f"/quizzes/{quiz_id}/questions", json=bad_mcq)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_add_mcq_only_one_option_returns_422(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]

    bad_mcq = {
        "type": "mcq",
        "prompt": "True or False?",
        "options": ["True"],
        "correct_answer": "True",
    }
    response = await client.post(f"/quizzes/{quiz_id}/questions", json=bad_mcq)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_add_mcq_missing_correct_answer_returns_422(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]

    bad_mcq = {
        "type": "mcq",
        "prompt": "Which is correct?",
        "options": ["A", "B"],
    }
    response = await client.post(f"/quizzes/{quiz_id}/questions", json=bad_mcq)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Add short-answer question
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_short_answer_question_returns_201(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]

    response = await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "short"
    assert data["options"] is None
    assert data["correct_answer"] is None


# ---------------------------------------------------------------------------
# Questions ordered by position
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_questions_ordered_by_position(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]

    await client.post(
        f"/quizzes/{quiz_id}/questions", json={**SHORT_PAYLOAD, "position": 2}
    )
    await client.post(
        f"/quizzes/{quiz_id}/questions", json={**MCQ_PAYLOAD, "position": 0}
    )
    await client.post(
        f"/quizzes/{quiz_id}/questions",
        json={"type": "short", "prompt": "Middle question", "position": 1},
    )

    response = await client.get(f"/quizzes/{quiz_id}")
    questions = response.json()["questions"]
    positions = [q["position"] for q in questions]
    assert positions == sorted(positions)


# ---------------------------------------------------------------------------
# Edit question
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_question_updates_prompt(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]

    q_resp = await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_PAYLOAD)
    q_id = q_resp.json()["id"]

    update = {"prompt": "Updated prompt text."}
    response = await client.put(f"/quizzes/{quiz_id}/questions/{q_id}", json=update)
    assert response.status_code == 200
    assert response.json()["prompt"] == "Updated prompt text."


@pytest.mark.asyncio
async def test_edit_question_not_found_returns_404(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]
    fake_q_id = "00000000-0000-0000-0000-000000000000"

    response = await client.put(
        f"/quizzes/{quiz_id}/questions/{fake_q_id}",
        json={"prompt": "Irrelevant"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete question
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_question_returns_204(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]

    q_resp = await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_PAYLOAD)
    q_id = q_resp.json()["id"]

    response = await client.delete(f"/quizzes/{quiz_id}/questions/{q_id}")
    assert response.status_code == 204

    # Verify deletion
    quiz_resp = await client.get(f"/quizzes/{quiz_id}")
    assert all(q["id"] != q_id for q in quiz_resp.json()["questions"])


@pytest.mark.asyncio
async def test_delete_question_not_found_returns_404(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]
    fake_q_id = "00000000-0000-0000-0000-000000000000"

    response = await client.delete(f"/quizzes/{quiz_id}/questions/{fake_q_id}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Publish quiz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_quiz_with_questions_returns_200(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]
    await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_PAYLOAD)

    response = await client.post(f"/quizzes/{quiz_id}/publish")

    assert response.status_code == 200
    assert response.json()["is_published"] is True


@pytest.mark.asyncio
async def test_publish_quiz_with_no_questions_returns_400(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]

    response = await client.post(f"/quizzes/{quiz_id}/publish")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_publish_quiz_is_idempotent(client: AsyncClient) -> None:
    create_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = create_resp.json()["id"]
    await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_PAYLOAD)
    await client.post(f"/quizzes/{quiz_id}/publish")

    response = await client.post(f"/quizzes/{quiz_id}/publish")

    assert response.status_code == 200
    assert response.json()["is_published"] is True


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_403() -> None:
    from httpx import ASGITransport

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as unauthed:
        response = await unauthed.post("/quizzes", json=QUIZ_PAYLOAD)
    assert response.status_code in (401, 403)
