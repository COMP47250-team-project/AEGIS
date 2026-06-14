"""Tests for GDPR consent endpoints (AEGIS-38).

Consent is recorded in student_sessions.consent_at. The frontend uses
GET /session to gate the exam shell and POST /consent to record agreement.
"""

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
    "title": "Consent Test Quiz",
    "description": "Quiz for AEGIS-38 tests.",
    "duration_minutes": 30,
}

SHORT_QUESTION = {
    "type": "short",
    "prompt": "What is TCP?",
}

EXAM_PAYLOAD = {
    "course_id": "CS102",
    "scheduled_start": "2026-09-01T09:00:00+00:00",
    "duration_minutes": 60,
}

STUDENT_ID = "student-consent-1"


def _student_client(student_id: str = STUDENT_ID) -> AsyncClient:
    token = jwt.encode(
        {"sub": student_id}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _setup_open_exam(client: AsyncClient) -> str:
    """Create quiz with one question, create exam, enroll student, open it."""
    quiz_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    assert quiz_resp.status_code == 201
    quiz_id = quiz_resp.json()["id"]

    q_resp = await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_QUESTION)
    assert q_resp.status_code == 201

    exam_resp = await client.post("/exams", json={**EXAM_PAYLOAD, "quiz_id": quiz_id})
    assert exam_resp.status_code == 201
    exam_id = exam_resp.json()["id"]

    enroll_resp = await client.post(
        f"/exams/{exam_id}/enrollments", json={"student_id": STUDENT_ID}
    )
    assert enroll_resp.status_code == 201

    open_resp = await client.post(f"/exams/{exam_id}/open")
    assert open_resp.status_code == 200

    return exam_id


# ---------------------------------------------------------------------------
# GET /exams/{exam_id}/session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_session_returns_null_consent_before_agreeing(client: AsyncClient) -> None:
    exam_id = await _setup_open_exam(client)

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/session")

    assert resp.status_code == 200
    data = resp.json()
    assert data["exam_id"] == exam_id
    assert data["student_id"] == STUDENT_ID
    assert data["consent_at"] is None


@pytest.mark.asyncio
async def test_get_session_is_idempotent(client: AsyncClient) -> None:
    """Fetching session twice does not create duplicate rows or change consent."""
    exam_id = await _setup_open_exam(client)

    async with _student_client() as student:
        first = await student.get(f"/exams/{exam_id}/session")
        second = await student.get(f"/exams/{exam_id}/session")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["consent_at"] is None


@pytest.mark.asyncio
async def test_get_session_nonexistent_exam_returns_404(client: AsyncClient) -> None:
    async with _student_client() as student:
        resp = await student.get(f"/exams/{uuid.uuid4()}/session")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_session_unauthenticated_returns_401_or_403() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as unauthed:
        resp = await unauthed.get(f"/exams/{uuid.uuid4()}/session")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /exams/{exam_id}/consent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_consent_sets_timestamp(client: AsyncClient) -> None:
    exam_id = await _setup_open_exam(client)

    async with _student_client() as student:
        resp = await student.post(f"/exams/{exam_id}/consent")

    assert resp.status_code == 200
    data = resp.json()
    assert data["exam_id"] == exam_id
    assert data["student_id"] == STUDENT_ID
    assert data["consent_at"] is not None


@pytest.mark.asyncio
async def test_record_consent_is_idempotent(client: AsyncClient) -> None:
    """Calling consent twice updates the timestamp but does not error."""
    exam_id = await _setup_open_exam(client)

    async with _student_client() as student:
        first = await student.post(f"/exams/{exam_id}/consent")
        second = await student.post(f"/exams/{exam_id}/consent")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["consent_at"] is not None


@pytest.mark.asyncio
async def test_session_reflects_consent_after_recording(client: AsyncClient) -> None:
    """GET /session after POST /consent returns consent_at set."""
    exam_id = await _setup_open_exam(client)

    async with _student_client() as student:
        await student.post(f"/exams/{exam_id}/consent")
        resp = await student.get(f"/exams/{exam_id}/session")

    assert resp.status_code == 200
    assert resp.json()["consent_at"] is not None


@pytest.mark.asyncio
async def test_record_consent_nonexistent_exam_returns_404(client: AsyncClient) -> None:
    async with _student_client() as student:
        resp = await student.post(f"/exams/{uuid.uuid4()}/consent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_record_consent_unauthenticated_returns_401_or_403() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as unauthed:
        resp = await unauthed.post(f"/exams/{uuid.uuid4()}/consent")
    assert resp.status_code in (401, 403)
