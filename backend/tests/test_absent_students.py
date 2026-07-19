"""AEGIS-118: enrolled students with zero telemetry must appear in the
professor's integrity report as "No telemetry / Absent" rather than being
omitted or flagged, and "Absent" must be distinguishable from "No Answer"
in the grade report.
"""

import csv
import io
import uuid

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.exam import Enrollment
from app.models.risk import RiskFlag
from app.models.telemetry import SessionScore
from app.services.scorer import compute_and_save_scores


def _student_headers(student_id: str) -> dict[str, str]:
    token = jwt.encode(
        {"sub": student_id, "role": "student"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}

QUIZ_PAYLOAD = {"title": "Absent Student Quiz", "duration_minutes": 30}
EXAM_PAYLOAD_TEMPLATE = {
    "course_id": "CS101",
    "scheduled_start": "2026-09-01T09:00:00+00:00",
    "duration_minutes": 60,
}


# ---------------------------------------------------------------------------
# Scorer: enrolled student with zero telemetry gets a real 0 score, not a flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrolled_student_with_no_telemetry_gets_zero_score_not_flagged(
    db_session: AsyncSession,
) -> None:
    exam_id = uuid.uuid4()
    student_id = str(uuid.uuid4())
    db_session.add(Enrollment(exam_id=exam_id, student_id=student_id))
    await db_session.commit()

    await compute_and_save_scores(db_session, exam_id)

    score = (
        await db_session.execute(
            select(SessionScore).where(
                SessionScore.exam_id == exam_id,
                SessionScore.student_id == student_id,
            )
        )
    ).scalar_one()
    assert score.integrity_score == pytest.approx(0.0)
    assert score.has_telemetry is False

    flags = (
        await db_session.execute(
            select(RiskFlag).where(
                RiskFlag.exam_id == exam_id, RiskFlag.student_id == student_id
            )
        )
    ).scalars().all()
    assert len(flags) == 0


# ---------------------------------------------------------------------------
# Grade report: Absent (no StudentSession, no answers) vs No Answer (attended,
# nothing submitted) vs a student who actually answered.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grade_report_distinguishes_absent_from_no_answer(
    client: AsyncClient,
) -> None:
    quiz_resp = await client.post("/quizzes", json=QUIZ_PAYLOAD)
    quiz_id = quiz_resp.json()["id"]
    await client.post(
        f"/quizzes/{quiz_id}/questions",
        json={"type": "short", "prompt": "Explain X.", "max_score": 10, "position": 0},
    )

    exam_id = (
        await client.post(
            "/exams", json={**EXAM_PAYLOAD_TEMPLATE, "quiz_id": quiz_id}
        )
    ).json()["id"]

    # get_exam_grade resolves student names via User.id, which requires
    # student_id to parse as a UUID (JWT sub is always a real user's UUID).
    absent_student = str(uuid.uuid4())
    no_answer_student = str(uuid.uuid4())
    await client.post(
        f"/exams/{exam_id}/enrollments", json={"student_id": absent_student}
    )
    await client.post(
        f"/exams/{exam_id}/enrollments", json={"student_id": no_answer_student}
    )
    await client.post(f"/exams/{exam_id}/open")

    # no_answer_student "joins" (creates a StudentSession) but submits nothing.
    await client.get(
        f"/exams/{exam_id}/session", headers=_student_headers(no_answer_student)
    )

    await client.post(f"/exams/{exam_id}/close")

    report = (await client.get(f"/exams/{exam_id}/grade")).json()
    by_id = {s["student_id"]: s for s in report["students"]}

    assert by_id[absent_student]["attended"] is False
    assert by_id[no_answer_student]["attended"] is True


@pytest.mark.asyncio
async def test_students_who_actually_answer_are_not_marked_absent(
    client: AsyncClient,
) -> None:
    """Reproduces the real professor flow end-to-end: register two real
    student accounts, enroll them by email (the UI's enrollment path), open
    the exam, each student answers and finishes, professor closes and views
    the grade report. Neither should show as Absent."""
    quiz_id = (await client.post("/quizzes", json=QUIZ_PAYLOAD)).json()["id"]
    mcq_id = (
        await client.post(
            f"/quizzes/{quiz_id}/questions",
            json={
                "type": "mcq",
                "prompt": "2 + 2?",
                "options": ["3", "4"],
                "correct_answer": "4",
                "max_score": 1,
                "position": 0,
            },
        )
    ).json()["id"]

    exam_id = (
        await client.post(
            "/exams", json={**EXAM_PAYLOAD_TEMPLATE, "quiz_id": quiz_id}
        )
    ).json()["id"]

    student_ids: list[str] = []
    for i in range(2):
        email = f"real-student-{i}-{uuid.uuid4().hex[:8]}@ucd.ie"
        reg = await client.post(
            "/auth/register",
            json={"email": email, "password": "StudentPass1", "role": "student"},
        )
        student_id = reg.json()["user"]["id"]
        student_ids.append(student_id)
        # Enroll-by-email is the professor UI's actual enrollment path.
        await client.post(
            f"/exams/{exam_id}/enroll-by-email", json={"email": email}
        )

    await client.post(f"/exams/{exam_id}/open")

    for student_id in student_ids:
        headers = _student_headers(student_id)
        # Mirrors ExamShell: fetch the session (lazily creates it), then
        # submit a final answer ("Finish Exam").
        await client.get(f"/exams/{exam_id}/session", headers=headers)
        resp = await client.post(
            f"/exams/{exam_id}/answers",
            json={
                "answers": [{"question_id": mcq_id, "answer": "4"}],
                "final": True,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    await client.post(f"/exams/{exam_id}/close")

    report = (await client.get(f"/exams/{exam_id}/grade")).json()
    by_id = {s["student_id"]: s for s in report["students"]}

    for student_id in student_ids:
        assert by_id[student_id]["attended"] is True, (
            f"student {student_id} should not be Absent"
        )
        assert by_id[student_id]["mcq_correct"] == 1


# ---------------------------------------------------------------------------
# CSV export: enrolled student with no telemetry appears with has_telemetry=NO
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_csv_export_includes_no_telemetry_student(client: AsyncClient) -> None:
    quiz_id = (await client.post("/quizzes", json=QUIZ_PAYLOAD)).json()["id"]
    exam_id = (
        await client.post(
            "/exams", json={**EXAM_PAYLOAD_TEMPLATE, "quiz_id": quiz_id}
        )
    ).json()["id"]

    student_id = "never-joined-student"
    await client.post(
        f"/exams/{exam_id}/enrollments", json={"student_id": student_id}
    )
    await client.post(f"/exams/{exam_id}/open")
    await client.post(f"/exams/{exam_id}/close")

    resp = await client.get(f"/exams/{exam_id}/export")
    assert resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    row = next(r for r in rows if r["student_id"] == student_id)
    assert row["has_telemetry"] == "NO"
    assert row["integrity_score"] == "0.0"
