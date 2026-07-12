"""Student-group tests: create, list, enroll-group, empty group, coexistence."""

import pytest
from httpx import AsyncClient

STUDENTS = [
    ("g1@demo.ac.uk", "G One"),
    ("g2@demo.ac.uk", "G Two"),
    ("g3@demo.ac.uk", "G Three"),
]


async def _register_students(client: AsyncClient) -> None:
    for email, name in STUDENTS:
        await client.post(
            "/auth/register",
            json={"email": email, "password": "demo1234", "role": "student", "name": name},
        )


async def _make_draft_exam(client: AsyncClient) -> str:
    quiz = (await client.post("/quizzes", json={"title": "G", "duration_minutes": 30})).json()
    await client.post(f"/quizzes/{quiz['id']}/questions", json={"type": "short", "prompt": "Q?"})
    await client.post(f"/quizzes/{quiz['id']}/publish")
    exam = (
        await client.post(
            "/exams",
            json={
                "quiz_id": quiz["id"],
                "course_id": "CS",
                "scheduled_start": "2026-09-01T09:00:00+00:00",
                "duration_minutes": 30,
            },
        )
    ).json()
    return exam["id"]


@pytest.mark.asyncio
async def test_create_group_with_three_students(client: AsyncClient) -> None:
    await _register_students(client)
    resp = await client.post(
        "/groups", json={"name": "CS 2026", "student_emails": [e for e, _ in STUDENTS]}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "CS 2026"
    assert {m["email"] for m in body["members"]} == {e for e, _ in STUDENTS}


@pytest.mark.asyncio
async def test_groups_persist_and_list(client: AsyncClient) -> None:
    await _register_students(client)
    await client.post("/groups", json={"name": "Listed", "student_emails": [STUDENTS[0][0]]})
    groups = (await client.get("/groups")).json()
    assert any(g["name"] == "Listed" and g["member_count"] == 1 for g in groups)


@pytest.mark.asyncio
async def test_enroll_group_adds_all_members(client: AsyncClient) -> None:
    await _register_students(client)
    gid = (
        await client.post(
            "/groups", json={"name": "E", "student_emails": [e for e, _ in STUDENTS]}
        )
    ).json()["id"]
    exam_id = await _make_draft_exam(client)
    resp = await client.post(f"/exams/{exam_id}/enroll-group", json={"group_id": gid})
    assert resp.status_code == 201
    assert resp.json()["enrolled"] == 3
    enrollments = (await client.get(f"/exams/{exam_id}/enrollments")).json()
    assert len(enrollments) == 3


@pytest.mark.asyncio
async def test_group_and_individual_enrollments_coexist(client: AsyncClient) -> None:
    await _register_students(client)
    gid = (
        await client.post(
            "/groups", json={"name": "C", "student_emails": [STUDENTS[0][0], STUDENTS[1][0]]}
        )
    ).json()["id"]
    exam_id = await _make_draft_exam(client)
    await client.post(f"/exams/{exam_id}/enroll-by-email", json={"email": STUDENTS[2][0]})
    await client.post(f"/exams/{exam_id}/enroll-group", json={"group_id": gid})
    enrollments = (await client.get(f"/exams/{exam_id}/enrollments")).json()
    assert len(enrollments) == 3


@pytest.mark.asyncio
async def test_empty_group_handled_gracefully(client: AsyncClient) -> None:
    gid = (
        await client.post(
            "/groups", json={"name": "Empty", "student_emails": ["nobody@example.com"]}
        )
    ).json()["id"]
    assert (await client.get(f"/groups/{gid}")).json()["members"] == []
    exam_id = await _make_draft_exam(client)
    resp = await client.post(f"/exams/{exam_id}/enroll-group", json={"group_id": gid})
    assert resp.status_code == 201
    assert resp.json() == {"enrolled": 0, "group_size": 0}
