"""Tests for the professor session dashboard endpoint (AEGIS-58, AEGIS-59)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import SessionScore, TelemetryEvent

QUIZ = {"title": "Dashboard Quiz", "description": "x", "duration_minutes": 30}
# Far-future start so this exam sorts to the top of the (scheduled_start desc)
# list — the shared in-memory test DB accumulates exams across the whole suite.
EXAM = {
    "course_id": "CS200",
    "scheduled_start": "2099-01-01T09:00:00+00:00",
    "duration_minutes": 60,
}


def _find(items: list[dict], exam_id: str) -> dict:
    matches = [s for s in items if s["id"] == exam_id]
    assert len(matches) == 1, f"exam {exam_id} not found in session list"
    return matches[0]


async def _open_exam_with_student(client: AsyncClient) -> str:
    quiz_id = (await client.post("/quizzes", json=QUIZ)).json()["id"]
    exam_id = (
        await client.post("/exams", json={**EXAM, "quiz_id": quiz_id})
    ).json()["id"]
    await client.post(f"/exams/{exam_id}/enrollments", json={"student_id": "student-001"})
    await client.post(f"/exams/{exam_id}/open")
    return exam_id


@pytest.mark.asyncio
async def test_active_sessions_include_student_and_flagged_counts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    exam_id = await _open_exam_with_student(client)
    # One student above the flagged threshold (0.7).
    db_session.add(
        SessionScore(
            exam_id=uuid.UUID(exam_id),
            student_id="student-001",
            integrity_score=0.85,
        )
    )
    await db_session.commit()

    resp = await client.get("/sessions?status=active&page_size=100")

    assert resp.status_code == 200
    session = _find(resp.json()["items"], exam_id)
    assert session["state"] == "open"
    assert session["student_count"] == 1
    assert session["flagged_count"] == 1
    assert session["quiz_title"] == "Dashboard Quiz"


@pytest.mark.asyncio
async def test_draft_exam_excluded_from_active(client: AsyncClient) -> None:
    quiz_id = (await client.post("/quizzes", json=QUIZ)).json()["id"]
    exam_id = (
        await client.post("/exams", json={**EXAM, "quiz_id": quiz_id})
    ).json()["id"]  # left in draft

    resp = await client.get("/sessions?status=active")

    ids = [s["id"] for s in resp.json()["items"]]
    assert exam_id not in ids


@pytest.mark.asyncio
async def test_low_score_students_not_flagged(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    exam_id = await _open_exam_with_student(client)
    db_session.add(
        SessionScore(
            exam_id=uuid.UUID(exam_id),
            student_id="student-001",
            integrity_score=0.3,  # below threshold
        )
    )
    await db_session.commit()

    resp = await client.get("/sessions?status=active&page_size=100")
    session = _find(resp.json()["items"], exam_id)
    assert session["student_count"] == 1
    assert session["flagged_count"] == 0


@pytest.mark.asyncio
async def test_pagination_metadata(client: AsyncClient) -> None:
    resp = await client.get("/sessions?status=active&page=1&page_size=5")
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert "total" in data
    assert isinstance(data["items"], list)


# ---------------------------------------------------------------------------
# AEGIS-59 — student event timeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_timeline_returns_events_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    quiz_id = (await client.post("/quizzes", json=QUIZ)).json()["id"]
    exam_id = (
        await client.post("/exams", json={**EXAM, "quiz_id": quiz_id})
    ).json()["id"]

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, etype in enumerate(["paste", "tab_blur", "resize"]):
        db_session.add(
            TelemetryEvent(
                exam_id=uuid.UUID(exam_id),
                student_id="stud-1",
                event_type=etype,
                payload={"i": i},
                occurred_at=base + timedelta(minutes=i),
            )
        )
    await db_session.commit()

    resp = await client.get(f"/sessions/{exam_id}/students/stud-1/events")

    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == "stud-1"
    assert data["total"] == 3
    # Most recent first.
    assert [e["event_type"] for e in data["items"]] == ["resize", "tab_blur", "paste"]


@pytest.mark.asyncio
async def test_timeline_unknown_session_returns_404(client: AsyncClient) -> None:
    resp = await client.get(f"/sessions/{uuid.uuid4()}/students/anyone/events")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Feature 2 — per-student score endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_score_not_available(client: AsyncClient) -> None:
    exam_id = await _open_exam_with_student(client)
    resp = await client.get(f"/sessions/{exam_id}/students/student-001/score")
    assert resp.status_code == 200
    assert resp.json()["available"] is False


@pytest.mark.asyncio
async def test_student_score_available(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    exam_id = await _open_exam_with_student(client)
    db_session.add(
        SessionScore(
            exam_id=uuid.UUID(exam_id),
            student_id="student-001",
            integrity_score=0.75,
            tab_switch_score=0.8,
            paste_score=0.6,
            keystroke_score=0.5,
            focus_loss_score=0.7,
            answer_timing_score=0.4,
            copy_sequence_score=0.3,
        )
    )
    await db_session.commit()

    resp = await client.get(f"/sessions/{exam_id}/students/student-001/score")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["integrity_score"] == pytest.approx(0.75)
    assert "Tab Switch" in data["components"]
    assert "Paste" in data["components"]
    assert data["components"]["Tab Switch"] == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Feature 4 — session scores list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_session_scores_returns_sorted_by_risk(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    exam_id = await _open_exam_with_student(client)
    db_session.add(
        SessionScore(
            exam_id=uuid.UUID(exam_id),
            student_id="student-001",
            integrity_score=0.85,
        )
    )
    await db_session.commit()

    resp = await client.get(f"/sessions/{exam_id}/scores")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["student_id"] == "student-001"
    assert data[0]["integrity_score"] == pytest.approx(0.85)
    assert data[0]["flagged"] is True


@pytest.mark.asyncio
async def test_list_session_scores_shows_enrolled_student_with_no_telemetry(
    client: AsyncClient,
) -> None:
    """AEGIS-118: an enrolled student with no SessionScore row (never produced
    telemetry) must still appear — with a real 0 score, unflagged — instead of
    being omitted."""
    exam_id = await _open_exam_with_student(client)
    resp = await client.get(f"/sessions/{exam_id}/scores")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["student_id"] == "student-001"
    assert data[0]["integrity_score"] == pytest.approx(0.0)
    assert data[0]["flagged"] is False
    assert data[0]["has_telemetry"] is False


@pytest.mark.asyncio
async def test_list_session_scores_not_owner_returns_404(
    client: AsyncClient,
) -> None:
    resp = await client.get(f"/sessions/{uuid.uuid4()}/scores")
    assert resp.status_code == 404
