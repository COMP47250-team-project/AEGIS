"""Tests for manual grading of short-answer questions (AEGIS-112a).

Locks in that a professor's score persists and that invalid attempts are
rejected with a clear status (the frontend now surfaces these instead of
failing silently).
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.main import app

# A real student id is a UUID (JWT sub = user.id); the grade report parses it
# as one, so use a valid UUID here.
STUDENT_ID = "11111111-1111-1111-1111-111111111111"


def _student_client() -> AsyncClient:
    token = jwt.encode(
        {"sub": STUDENT_ID, "role": "student"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _setup_exam_with_answer(
    client: AsyncClient, *, close: bool, max_score: int = 10
) -> tuple[str, str]:
    """Create a quiz with one short question, enroll the student, open the exam,
    have the student submit an answer, optionally close. Returns (exam_id,
    answer_id-or-empty)."""
    quiz_id = (
        await client.post(
            "/quizzes", json={"title": "Grade Quiz", "duration_minutes": 30}
        )
    ).json()["id"]
    short_q_id = (
        await client.post(
            f"/quizzes/{quiz_id}/questions",
            json={
                "type": "short",
                "prompt": "Explain something.",
                "max_score": max_score,
                "position": 0,
            },
        )
    ).json()["id"]
    exam_id = (
        await client.post(
            "/exams",
            json={
                "course_id": "CS",
                "scheduled_start": "2026-09-01T09:00:00+00:00",
                "duration_minutes": 60,
                "quiz_id": quiz_id,
            },
        )
    ).json()["id"]
    await client.post(
        f"/exams/{exam_id}/enrollments", json={"student_id": STUDENT_ID}
    )
    await client.post(f"/exams/{exam_id}/open")

    async with _student_client() as student:
        await student.post(
            f"/exams/{exam_id}/answers",
            json={"answers": [{"question_id": short_q_id, "answer": "my essay"}]},
        )

    if not close:
        return exam_id, ""

    await client.post(f"/exams/{exam_id}/close")
    report = (await client.get(f"/exams/{exam_id}/grade")).json()
    answer_id = report["students"][0]["answers"][0]["answer_id"]
    return exam_id, answer_id


@pytest.mark.asyncio
async def test_manual_grade_persists(client: AsyncClient) -> None:
    exam_id, answer_id = await _setup_exam_with_answer(client, close=True)

    resp = await client.patch(
        f"/exams/{exam_id}/answers/grade",
        json={"answer_id": answer_id, "score": 8},
    )
    assert resp.status_code == 200
    assert resp.json()["manual_score"] == 8

    # Persisted: the grade report now reports the saved score.
    report = (await client.get(f"/exams/{exam_id}/grade")).json()
    graded = report["students"][0]["answers"][0]
    assert graded["manual_score"] == 8


@pytest.mark.asyncio
async def test_manual_grade_above_max_is_rejected(client: AsyncClient) -> None:
    exam_id, answer_id = await _setup_exam_with_answer(
        client, close=True, max_score=10
    )
    resp = await client.patch(
        f"/exams/{exam_id}/answers/grade",
        json={"answer_id": answer_id, "score": 11},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_manual_grade_on_open_exam_is_rejected(client: AsyncClient) -> None:
    exam_id, _ = await _setup_exam_with_answer(client, close=False)
    resp = await client.patch(
        f"/exams/{exam_id}/answers/grade",
        json={"answer_id": str(uuid.uuid4()), "score": 5},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_results_hidden_until_released_for_mixed_exam(
    client: AsyncClient,
) -> None:
    exam_id, answer_id = await _setup_exam_with_answer(client, close=True)

    # Before release: the student sees "under review" — scores redacted.
    async with _student_client() as student:
        before = (await student.get(f"/student/exams/{exam_id}/results")).json()
    assert before["results_released"] is False
    assert before["points_earned"] == 0

    # Professor grades then releases.
    await client.patch(
        f"/exams/{exam_id}/answers/grade",
        json={"answer_id": answer_id, "score": 8},
    )
    released = (await client.post(f"/exams/{exam_id}/release-results")).json()
    assert released["results_released"] is True

    # After release: the student sees the score.
    async with _student_client() as student:
        after = (await student.get(f"/student/exams/{exam_id}/results")).json()
    assert after["results_released"] is True
    assert after["points_earned"] == 8


@pytest.mark.asyncio
async def test_release_blocked_when_ungraded_short_answers_remain(
    client: AsyncClient,
) -> None:
    """AEGIS-112b: release must be rejected while a gradable answer is
    ungraded, with an actionable count in the error."""
    exam_id, _ = await _setup_exam_with_answer(client, close=True)

    resp = await client.post(f"/exams/{exam_id}/release-results")
    assert resp.status_code == 409
    assert "1 answer" in resp.json()["detail"]

    report = (await client.get(f"/exams/{exam_id}/grade")).json()
    assert report["results_released"] is False


@pytest.mark.asyncio
async def test_release_succeeds_once_all_answers_graded(
    client: AsyncClient,
) -> None:
    """AEGIS-112b: once every gradable answer has a score, release succeeds
    and stamps results_released_at (surfaced via results_released)."""
    exam_id, answer_id = await _setup_exam_with_answer(client, close=True)

    await client.patch(
        f"/exams/{exam_id}/answers/grade",
        json={"answer_id": answer_id, "score": 7},
    )

    resp = await client.post(f"/exams/{exam_id}/release-results")
    assert resp.status_code == 200
    assert resp.json()["results_released"] is True

    report = (await client.get(f"/exams/{exam_id}/grade")).json()
    assert report["results_released"] is True


@pytest.mark.asyncio
async def test_results_ready_flag_in_student_list(client: AsyncClient) -> None:
    exam_id, answer_id = await _setup_exam_with_answer(client, close=True)

    # Mixed exam, not released -> not ready in the dashboard list.
    async with _student_client() as student:
        items = (await student.get("/student/sessions")).json()
    item = next(i for i in items if i["exam_id"] == exam_id)
    assert item["results_ready"] is False

    await client.patch(
        f"/exams/{exam_id}/answers/grade",
        json={"answer_id": answer_id, "score": 5},
    )
    await client.post(f"/exams/{exam_id}/release-results")

    async with _student_client() as student:
        items = (await student.get("/student/sessions")).json()
    item = next(i for i in items if i["exam_id"] == exam_id)
    assert item["results_ready"] is True
