"""Tests for the question-bank endpoint (AEGIS-90).

The test DB is shared across the suite (no per-test isolation), so each test
tags its questions with a unique marker and asserts via search on that marker
rather than relying on global totals.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.main import app


def _client(user_id: str, role: str = "professor") -> AsyncClient:
    token = jwt.encode(
        {"sub": user_id, "role": role},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _make_quiz(client: AsyncClient, marker: str) -> None:
    quiz_id = (
        await client.post(
            "/quizzes", json={"title": f"Bank Quiz {marker}", "duration_minutes": 30}
        )
    ).json()["id"]
    await client.post(
        f"/quizzes/{quiz_id}/questions",
        json={"type": "short", "prompt": f"Explain TCP {marker}", "position": 0},
    )
    await client.post(
        f"/quizzes/{quiz_id}/questions",
        json={
            "type": "mcq",
            "prompt": f"Which layer is IP {marker}",
            "options": ["Application", "Network"],
            "correct_answer": "Network",
            "position": 1,
        },
    )


@pytest.mark.asyncio
async def test_question_bank_returns_professor_questions(client: AsyncClient) -> None:
    marker = uuid.uuid4().hex[:8]
    await _make_quiz(client, marker)

    res = await client.get(
        "/quizzes/question-bank", params={"search": marker, "page_size": 100}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2

    mcq = next(i for i in body["items"] if i["question_type"] == "mcq")
    assert mcq["options"] == ["Application", "Network"]
    assert mcq["correct_answer"] == "Network"
    assert mcq["quiz_title"] == f"Bank Quiz {marker}"
    assert "created_at" in mcq


@pytest.mark.asyncio
async def test_question_bank_empty_for_professor_without_quizzes(
    client: AsyncClient,
) -> None:
    # `client` (prof-001) owns quizzes; a professor who never created any sees none.
    await _make_quiz(client, uuid.uuid4().hex[:8])

    async with _client("prof-none-999") as other:
        res = await other.get("/quizzes/question-bank")

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.asyncio
async def test_question_bank_search_filters_by_text(client: AsyncClient) -> None:
    marker = uuid.uuid4().hex[:8]
    await _make_quiz(client, marker)

    # The full phrase is unique to this test's short question — exactly one match.
    res = await client.get(
        "/quizzes/question-bank", params={"search": f"Explain TCP {marker}"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["question_text"] == f"Explain TCP {marker}"


@pytest.mark.asyncio
async def test_question_bank_forbidden_for_students(client: AsyncClient) -> None:
    async with _client("student-1", role="student") as student:
        res = await student.get("/quizzes/question-bank")
    assert res.status_code == 403
