"""Regression test for AEGIS-117 — past start time validation."""

import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db


@pytest.fixture
async def auth_client(db_session):
    """Authenticated professor client."""

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as ac:
        # Register and login as professor
        await ac.post(
            "/auth/register",
            json={
                "email": "prof117@test.com",
                "password": "Test1234!",
                "role": "professor",
                "name": "Prof Test",
            },
        )
        res = await ac.post(
            "/auth/login", json={"email": "prof117@test.com", "password": "Test1234!"}
        )
        token = res.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"

        # Create a quiz first
        quiz_res = await ac.post(
            "/quizzes", json={"title": "Test Quiz", "duration_minutes": 60}
        )
        ac.quiz_id = str(quiz_res.json()["id"])
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_exam_with_past_start_returns_422(auth_client):
    """Creating an exam with a past scheduled_start must return 422."""
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    res = await auth_client.post(
        "/exams",
        json={
            "quiz_id": auth_client.quiz_id,
            "course_id": "CS101",
            "scheduled_start": past_time,
            "duration_minutes": 60,
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_exam_with_future_start_succeeds(auth_client):
    """Creating an exam with a future scheduled_start must succeed."""
    future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    res = await auth_client.post(
        "/exams",
        json={
            "quiz_id": auth_client.quiz_id,
            "course_id": "CS101",
            "scheduled_start": future_time,
            "duration_minutes": 60,
        },
    )
    assert res.status_code == 201
