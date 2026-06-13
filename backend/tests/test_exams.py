"""Tests for exam session lifecycle endpoints (AEGIS-34)."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

QUIZ_PAYLOAD = {
    "title": "Exam Lifecycle Quiz",
    "description": "Used by exam lifecycle tests.",
    "duration_minutes": 30,
}

EXAM_PAYLOAD_TEMPLATE = {
    "course_id": "CS101",
    "scheduled_start": "2026-09-01T09:00:00+00:00",
    "duration_minutes": 60,
}

STUDENT_A = {"student_id": "student-001"}
STUDENT_B = {"student_id": "student-002"}


async def _create_quiz(client: AsyncClient) -> str:
    resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_exam(client: AsyncClient, quiz_id: str) -> str:
    payload = {**EXAM_PAYLOAD_TEMPLATE, "quiz_id": quiz_id}
    resp = await client.post("/exams", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def _other_client() -> AsyncClient:
    """Return an AsyncClient authenticated as a different professor.

    Relies on the `client` fixture having already registered the get_db override.
    Creates only a new HTTP client with a different JWT — does not touch overrides.
    """
    token = jwt.encode(
        {"sub": "other-prof-999"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


# ---------------------------------------------------------------------------
# Create exam
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_exam_returns_201(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    payload = {**EXAM_PAYLOAD_TEMPLATE, "quiz_id": quiz_id}

    response = await client.post("/exams", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["quiz_id"] == quiz_id
    assert data["course_id"] == "CS101"
    assert data["state"] == "draft"
    assert data["enrollment_count"] == 0
    assert "id" in data


@pytest.mark.asyncio
async def test_create_exam_missing_fields_returns_422(client: AsyncClient) -> None:
    response = await client.post("/exams", json={"course_id": "CS101"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Get exam
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_exam_returns_state_and_enrollment_count(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)

    response = await client.get(f"/exams/{exam_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == exam_id
    assert data["state"] == "draft"
    assert data["enrollment_count"] == 0


@pytest.mark.asyncio
async def test_get_exam_not_found_returns_404(client: AsyncClient) -> None:
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/exams/{fake_id}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enroll_student_returns_201(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)

    response = await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)

    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == STUDENT_A["student_id"]
    assert data["exam_id"] == exam_id


@pytest.mark.asyncio
async def test_enrollment_reflected_in_enrollment_count(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)

    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)
    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_B)

    response = await client.get(f"/exams/{exam_id}")
    assert response.json()["enrollment_count"] == 2


@pytest.mark.asyncio
async def test_duplicate_enrollment_returns_409(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)

    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)
    response = await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_enroll_student_in_open_exam_returns_409(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)
    await client.post(f"/exams/{exam_id}/open")

    response = await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_B)
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Open exam
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_exam_with_no_enrollments_returns_400(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)

    response = await client.post(f"/exams/{exam_id}/open")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_open_exam_transitions_to_open(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)

    response = await client.post(f"/exams/{exam_id}/open")

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "open"
    assert data["opened_at"] is not None


@pytest.mark.asyncio
async def test_open_exam_is_idempotent(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)
    await client.post(f"/exams/{exam_id}/open")

    response = await client.post(f"/exams/{exam_id}/open")

    assert response.status_code == 200
    assert response.json()["state"] == "open"


# ---------------------------------------------------------------------------
# Close exam
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_exam_transitions_to_closed(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)
    await client.post(f"/exams/{exam_id}/open")

    response = await client.post(f"/exams/{exam_id}/close")

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "closed"
    assert data["closed_at"] is not None


@pytest.mark.asyncio
async def test_close_exam_is_idempotent(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)
    await client.post(f"/exams/{exam_id}/open")
    await client.post(f"/exams/{exam_id}/close")

    response = await client.post(f"/exams/{exam_id}/close")

    assert response.status_code == 200
    assert response.json()["state"] == "closed"


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_closed_exam_returns_409(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)
    await client.post(f"/exams/{exam_id}/open")
    await client.post(f"/exams/{exam_id}/close")

    response = await client.post(f"/exams/{exam_id}/open")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_close_draft_exam_returns_409(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)

    response = await client.post(f"/exams/{exam_id}/close")

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Ownership guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_exam_forbidden_for_non_owner(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)

    async with _other_client() as other:
        response = await other.post(f"/exams/{exam_id}/open")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_close_exam_forbidden_for_non_owner(client: AsyncClient) -> None:
    quiz_id = await _create_quiz(client)
    exam_id = await _create_exam(client, quiz_id)
    await client.post(f"/exams/{exam_id}/enrollments", json=STUDENT_A)
    await client.post(f"/exams/{exam_id}/open")

    async with _other_client() as other:
        response = await other.post(f"/exams/{exam_id}/close")

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401_or_403() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as unauthed:
        response = await unauthed.post("/exams", json={})
    assert response.status_code in (401, 403)
