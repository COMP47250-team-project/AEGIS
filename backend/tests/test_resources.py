"""Tests for open-book exam resources + access tracking (AEGIS-121).

Covers: exam mode round-trip, professor allowlist CRUD (owner-only, draft-only),
URL scheme validation, file upload validation, student resource listing gated by
mode/enrollment/state, durable resource-access recording, and the aggregated
professor report. File-serving RBAC (enrolled student vs owner vs stranger) is
exercised via the local-disk fallback (no Azure required in CI).
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.main import app

QUIZ_PAYLOAD = {
    "title": "Open-Book Quiz",
    "description": "Quiz for AEGIS-121 tests.",
    "duration_minutes": 30,
}

SHORT_QUESTION = {"type": "short", "prompt": "Explain HTTP caching."}

EXAM_PAYLOAD = {
    "course_id": "CS101",
    "scheduled_start": "2026-09-01T09:00:00+00:00",
    "duration_minutes": 60,
}

STUDENT_ID = "student-200"
OTHER_STUDENT_ID = "student-999"


def _client_for(user_id: str, role: str) -> AsyncClient:
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


def _student_client(user_id: str = STUDENT_ID) -> AsyncClient:
    return _client_for(user_id, "student")


async def _create_open_book_draft(client: AsyncClient) -> str:
    """Create an open-book exam in draft state with one enrolled student.

    Returns the exam_id. The exam is NOT opened (so resource mutations, which
    are draft-only, still work).
    """
    quiz_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    assert quiz_resp.status_code == 201
    quiz_id = quiz_resp.json()["id"]

    q_resp = await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_QUESTION)
    assert q_resp.status_code == 201

    exam_resp = await client.post(
        "/exams", json={**EXAM_PAYLOAD, "quiz_id": quiz_id, "mode": "open_book"}
    )
    assert exam_resp.status_code == 201
    exam_id = exam_resp.json()["id"]

    enroll_resp = await client.post(
        f"/exams/{exam_id}/enrollments", json={"student_id": STUDENT_ID}
    )
    assert enroll_resp.status_code == 201
    return exam_id


# ---------------------------------------------------------------------------
# Exam mode round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exam_defaults_to_closed_book(client: AsyncClient) -> None:
    quiz_id = (await client.post("/quizzes", json=QUIZ_PAYLOAD)).json()["id"]
    resp = await client.post("/exams", json={**EXAM_PAYLOAD, "quiz_id": quiz_id})
    assert resp.status_code == 201
    assert resp.json()["mode"] == "closed_book"


@pytest.mark.asyncio
async def test_exam_open_book_mode_round_trips(client: AsyncClient) -> None:
    quiz_id = (await client.post("/quizzes", json=QUIZ_PAYLOAD)).json()["id"]
    resp = await client.post(
        "/exams", json={**EXAM_PAYLOAD, "quiz_id": quiz_id, "mode": "open_book"}
    )
    assert resp.status_code == 201
    exam_id = resp.json()["id"]
    assert resp.json()["mode"] == "open_book"

    got = await client.get(f"/exams/{exam_id}")
    assert got.json()["mode"] == "open_book"


# ---------------------------------------------------------------------------
# Professor allowlist CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_professor_adds_and_lists_url_resource(client: AsyncClient) -> None:
    exam_id = await _create_open_book_draft(client)

    add = await client.post(
        f"/exams/{exam_id}/resources",
        json={
            "label": "MDN HTTP caching",
            "url": "https://developer.mozilla.org",
            "embed": True,
        },
    )
    assert add.status_code == 201
    body = add.json()
    assert body["type"] == "url"
    assert body["url"] == "https://developer.mozilla.org"
    assert body["embed"] is True

    listed = await client.get(f"/exams/{exam_id}/resources")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["label"] == "MDN HTTP caching"


@pytest.mark.asyncio
async def test_url_scheme_validation_rejects_javascript(client: AsyncClient) -> None:
    exam_id = await _create_open_book_draft(client)
    resp = await client.post(
        f"/exams/{exam_id}/resources",
        json={"label": "evil", "url": "javascript:alert(1)"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_resource(client: AsyncClient) -> None:
    exam_id = await _create_open_book_draft(client)
    rid = (
        await client.post(
            f"/exams/{exam_id}/resources",
            json={"label": "Doc", "url": "https://example.com"},
        )
    ).json()["id"]

    delete = await client.delete(f"/exams/{exam_id}/resources/{rid}")
    assert delete.status_code == 204

    listed = await client.get(f"/exams/{exam_id}/resources")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_add_resource_owner_only(client: AsyncClient) -> None:
    """A different professor cannot add resources to someone else's exam."""
    exam_id = await _create_open_book_draft(client)
    async with _client_for("prof-other", "professor") as other_prof:
        resp = await other_prof.post(
            f"/exams/{exam_id}/resources",
            json={"label": "x", "url": "https://example.com"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_add_resource_requires_professor_role(client: AsyncClient) -> None:
    exam_id = await _create_open_book_draft(client)
    async with _student_client() as student:
        resp = await student.post(
            f"/exams/{exam_id}/resources",
            json={"label": "x", "url": "https://example.com"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_mutate_resources_after_open(client: AsyncClient) -> None:
    """Resources are draft-only — no changes once the exam is open."""
    exam_id = await _create_open_book_draft(client)
    await client.post(f"/exams/{exam_id}/open")

    resp = await client.post(
        f"/exams/{exam_id}/resources",
        json={"label": "late", "url": "https://example.com"},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# File upload validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_upload_rejects_non_pdf(client: AsyncClient) -> None:
    exam_id = await _create_open_book_draft(client)
    resp = await client.post(
        f"/exams/{exam_id}/resources/file",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_file_upload_and_serve_pdf(client: AsyncClient) -> None:
    """A professor uploads a PDF; the enrolled student can fetch it inline."""
    exam_id = await _create_open_book_draft(client)
    pdf_bytes = b"%PDF-1.4 fake pdf body"
    up = await client.post(
        f"/exams/{exam_id}/resources/file",
        data={"label": "Lecture 3"},
        files={"file": ("lecture3.pdf", pdf_bytes, "application/pdf")},
    )
    assert up.status_code == 201
    resource = up.json()
    assert resource["type"] == "file"
    rid = resource["id"]

    # Open the exam and consent so the student can access.
    await client.post(f"/exams/{exam_id}/open")
    async with _student_client() as student:
        await student.post(f"/exams/{exam_id}/consent")
        served = await student.get(f"/exams/{exam_id}/resources/{rid}/file")

    assert served.status_code == 200
    assert served.headers["content-type"].startswith("application/pdf")
    assert served.headers.get("x-content-type-options") == "nosniff"
    assert served.content == pdf_bytes


# ---------------------------------------------------------------------------
# Student resource listing — gated by mode / enrollment / state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_closed_book_exam_has_no_resource_access_for_students(
    client: AsyncClient,
) -> None:
    """A closed-book exam rejects the student resource listing."""
    quiz_id = (await client.post("/quizzes", json=QUIZ_PAYLOAD)).json()["id"]
    await client.post(f"/quizzes/{quiz_id}/questions", json=SHORT_QUESTION)
    exam_id = (
        await client.post("/exams", json={**EXAM_PAYLOAD, "quiz_id": quiz_id})
    ).json()["id"]
    await client.post(f"/exams/{exam_id}/enrollments", json={"student_id": STUDENT_ID})
    await client.post(f"/exams/{exam_id}/open")

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/resources")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_student_lists_resources_when_open_book_and_open(
    client: AsyncClient,
) -> None:
    exam_id = await _create_open_book_draft(client)
    await client.post(
        f"/exams/{exam_id}/resources",
        json={"label": "Docs", "url": "https://example.com"},
    )
    await client.post(f"/exams/{exam_id}/open")

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/resources")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_non_enrolled_student_cannot_list_resources(client: AsyncClient) -> None:
    exam_id = await _create_open_book_draft(client)
    await client.post(f"/exams/{exam_id}/open")

    async with _student_client(OTHER_STUDENT_ID) as stranger:
        resp = await stranger.get(f"/exams/{exam_id}/resources")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Resource-access recording + aggregation
# ---------------------------------------------------------------------------


async def _open_exam_with_resource(client: AsyncClient) -> tuple[str, str]:
    """Open-book exam, opened, with a single URL resource. Returns (exam_id, rid)."""
    exam_id = await _create_open_book_draft(client)
    rid = (
        await client.post(
            f"/exams/{exam_id}/resources",
            json={"label": "Docs", "url": "https://example.com/article"},
        )
    ).json()["id"]
    await client.post(f"/exams/{exam_id}/open")
    return exam_id, rid


@pytest.mark.asyncio
async def test_record_resource_access(client: AsyncClient) -> None:
    exam_id, rid = await _open_exam_with_resource(client)

    async with _student_client() as student:
        await student.post(f"/exams/{exam_id}/consent")
        resp = await student.post(
            f"/exams/{exam_id}/resource-access",
            json={"resource_id": rid},
        )
    assert resp.status_code == 201
    assert resp.json()["recorded"] is True
    assert resp.json()["id"]


@pytest.mark.asyncio
async def test_resource_access_duration_patch(client: AsyncClient) -> None:
    """Opening creates a row; the PATCH fills in its duration."""
    exam_id, rid = await _open_exam_with_resource(client)

    async with _student_client() as student:
        await student.post(f"/exams/{exam_id}/consent")
        opened = await student.post(
            f"/exams/{exam_id}/resource-access",
            json={"resource_id": rid},
        )
        access_id = opened.json()["id"]
        patched = await student.patch(
            f"/exams/{exam_id}/resource-access/{access_id}",
            json={"duration_ms": 4200},
        )
    assert patched.status_code == 200

    report = await client.get(f"/exams/{exam_id}/resource-access")
    usage = report.json()["students"][0]["resources"][0]
    assert usage["open_count"] == 1
    assert usage["total_duration_ms"] == 4200


@pytest.mark.asyncio
async def test_resource_access_report_aggregates_opens(client: AsyncClient) -> None:
    exam_id, rid = await _open_exam_with_resource(client)

    async with _student_client() as student:
        await student.post(f"/exams/{exam_id}/consent")
        first = await student.post(
            f"/exams/{exam_id}/resource-access",
            json={"resource_id": rid},
        )
        await student.patch(
            f"/exams/{exam_id}/resource-access/{first.json()['id']}",
            json={"duration_ms": 3000},
        )
        second = await student.post(
            f"/exams/{exam_id}/resource-access",
            json={"resource_id": rid},
        )
        await student.patch(
            f"/exams/{exam_id}/resource-access/{second.json()['id']}",
            json={"duration_ms": 4000},
        )

    report = await client.get(f"/exams/{exam_id}/resource-access")
    assert report.status_code == 200
    students = report.json()["students"]
    assert len(students) == 1
    usage = students[0]["resources"][0]
    assert usage["open_count"] == 2
    assert usage["total_duration_ms"] == 7000
    assert usage["label"] == "Docs"


@pytest.mark.asyncio
async def test_resource_access_report_owner_only(client: AsyncClient) -> None:
    exam_id, _ = await _open_exam_with_resource(client)
    async with _client_for("prof-other", "professor") as other_prof:
        resp = await other_prof.get(f"/exams/{exam_id}/resource-access")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_resource_access_rejected_after_submit(client: AsyncClient) -> None:
    """Once the student submits, recording further access is rejected."""
    exam_id, rid = await _open_exam_with_resource(client)
    # Need a question id to finalise; fetch the student's questions.
    async with _student_client() as student:
        await student.post(f"/exams/{exam_id}/consent")
        questions = await student.get(f"/exams/{exam_id}/questions")
        q_id = questions.json()[0]["id"]
        await student.post(
            f"/exams/{exam_id}/answers",
            json={"answers": [{"question_id": q_id, "answer": "done"}], "final": True},
        )
        resp = await student.post(
            f"/exams/{exam_id}/resource-access",
            json={"resource_id": rid},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_resource_access_rejects_foreign_resource(client: AsyncClient) -> None:
    """A resource_id from a different exam is a 404."""
    exam_id, _ = await _open_exam_with_resource(client)
    async with _student_client() as student:
        await student.post(f"/exams/{exam_id}/consent")
        resp = await student.post(
            f"/exams/{exam_id}/resource-access",
            json={"resource_id": str(uuid.uuid4())},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Student session exposes mode (so the panel knows when to render)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_session_reports_open_book_mode(client: AsyncClient) -> None:
    exam_id = await _create_open_book_draft(client)
    await client.post(f"/exams/{exam_id}/open")

    async with _student_client() as student:
        resp = await student.get(f"/exams/{exam_id}/session")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "open_book"
