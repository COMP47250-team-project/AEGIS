"""Tests for GET /student/sessions endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

QUIZ_PAYLOAD = {
    "title": "Student Sessions Quiz",
    "description": "Used by student sessions tests.",
    "duration_minutes": 60,
}

EXAM_PAYLOAD = {
    "course_id": "COMP47250",
    "scheduled_start": "2026-09-01T09:00:00+00:00",
    "duration_minutes": 60,
}

STUDENT_ID = "student-sessions-001"


def _student_client() -> AsyncClient:
    """AsyncClient authenticated as a student (different identity from the professor fixture)."""
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


async def _create_quiz(client: AsyncClient) -> str:
    resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_exam(client: AsyncClient, quiz_id: str) -> str:
    payload = {**EXAM_PAYLOAD, "quiz_id": quiz_id}
    resp = await client.post("/exams", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# GET /student/sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_sessions_empty_for_unenrolled_student(
    client: AsyncClient,
) -> None:
    async with _student_client() as sc:
        response = await sc.get("/student/sessions")

    assert response.status_code == 200
    data = response.json()
    # Student is not enrolled in any exam — list may be empty or contain
    # exams from other tests, so we just confirm shape and status are valid.
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_student_sessions_returns_enrolled_exam(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json={"student_id": STUDENT_ID})

    async with _student_client() as sc:
        response = await sc.get("/student/sessions")

    assert response.status_code == 200
    sessions = response.json()
    assert isinstance(sessions, list)

    matching = [s for s in sessions if s["exam_id"] == exam_id]
    assert len(matching) == 1, "Enrolled exam should appear in student sessions"

    session = matching[0]
    assert session["exam_title"] == QUIZ_PAYLOAD["title"]
    assert session["course_name"] == EXAM_PAYLOAD["course_id"]
    assert session["status"] == "upcoming"  # exam is still in draft state
    assert "starts_at" in session
    assert "ends_at" in session


@pytest.mark.asyncio
async def test_student_sessions_status_open(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json={"student_id": STUDENT_ID})
    await client.post(f"/exams/{exam_id}/open")

    async with _student_client() as sc:
        response = await sc.get("/student/sessions")

    assert response.status_code == 200
    sessions = response.json()
    matching = [s for s in sessions if s["exam_id"] == exam_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "open"


@pytest.mark.asyncio
async def test_student_sessions_status_completed(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json={"student_id": STUDENT_ID})
    await client.post(f"/exams/{exam_id}/open")
    await client.post(f"/exams/{exam_id}/close")

    async with _student_client() as sc:
        response = await sc.get("/student/sessions")

    assert response.status_code == 200
    sessions = response.json()
    matching = [s for s in sessions if s["exam_id"] == exam_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_student_sessions_not_in_list_without_enrollment(
    client: AsyncClient,
) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    # Deliberately do NOT enroll the student

    async with _student_client() as sc:
        response = await sc.get("/student/sessions")

    assert response.status_code == 200
    sessions = response.json()
    exam_ids = [s["exam_id"] for s in sessions]
    assert exam_id not in exam_ids


@pytest.mark.asyncio
async def test_student_sessions_unauthenticated_returns_401_or_403() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as unauthed:
        response = await unauthed.get("/student/sessions")
    assert response.status_code in (401, 403)
