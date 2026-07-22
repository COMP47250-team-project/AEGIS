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
    # AEGIS-119: response now also reports already-enrolled members (none here).
    assert resp.json() == {"enrolled": 0, "group_size": 0, "skipped": []}


@pytest.mark.asyncio
async def test_create_group_reports_skipped_emails(client: AsyncClient) -> None:
    await _register_students(client)
    resp = await client.post(
        "/groups",
        json={
            "name": "Mixed",
            "student_emails": [
                STUDENTS[0][0],       # registered -> added
                STUDENTS[0][0],       # duplicate -> skipped
                "ghost@demo.ac.uk",   # not registered -> skipped
                "not-an-email",       # invalid format -> skipped
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert {m["email"] for m in body["members"]} == {STUDENTS[0][0]}
    reasons = {s["email"]: s["reason"] for s in body["skipped"]}
    assert reasons[STUDENTS[0][0]] == "Duplicate entry skipped."
    assert "not registered" in reasons["ghost@demo.ac.uk"]
    assert reasons["not-an-email"] == "Please enter a valid email address."


@pytest.mark.asyncio
async def test_validate_reports_without_creating(client: AsyncClient) -> None:
    await _register_students(client)
    before = len((await client.get("/groups")).json())
    resp = await client.post(
        "/groups/validate",
        json={"student_emails": [STUDENTS[0][0], "ghost@demo.ac.uk", "bad"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert {m["email"] for m in body["matched"]} == {STUDENTS[0][0]}
    assert {s["email"] for s in body["skipped"]} == {"ghost@demo.ac.uk", "bad"}
    # dry run must not create anything
    assert len((await client.get("/groups")).json()) == before


@pytest.mark.asyncio
async def test_update_members_add_remove_and_skip(client: AsyncClient) -> None:
    await _register_students(client)
    gid = (
        await client.post("/groups", json={"name": "EditMembers", "student_emails": [STUDENTS[0][0]]})
    ).json()["id"]
    resp = await client.put(
        f"/groups/{gid}/members",
        json={"add": [STUDENTS[1][0], STUDENTS[0][0], "ghost@demo.ac.uk"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert {m["email"] for m in body["members"]} == {STUDENTS[0][0], STUDENTS[1][0]}
    reasons = {s["email"]: s["reason"] for s in body["skipped"]}
    assert reasons[STUDENTS[0][0]] == "Already in the group."
    assert "not registered" in reasons["ghost@demo.ac.uk"]

    removed = await client.put(f"/groups/{gid}/members", json={"remove": [STUDENTS[0][0]]})
    assert {m["email"] for m in removed.json()["members"]} == {STUDENTS[1][0]}


@pytest.mark.asyncio
async def test_delete_group(client: AsyncClient) -> None:
    await _register_students(client)
    gid = (
        await client.post("/groups", json={"name": "Temp", "student_emails": [STUDENTS[0][0]]})
    ).json()["id"]
    resp = await client.delete(f"/groups/{gid}")
    assert resp.status_code == 204
    assert (await client.get(f"/groups/{gid}")).status_code == 404
    assert all(g["id"] != gid for g in (await client.get("/groups")).json())


@pytest.mark.asyncio
async def test_duplicate_group_name_rejected(client: AsyncClient) -> None:
    await _register_students(client)
    r1 = await client.post("/groups", json={"name": "Computer Science 123", "student_emails": []})
    assert r1.status_code == 201
    # exact and case-insensitive duplicates are both rejected
    for dup in ("Computer Science 123", "computer science 123", "  Computer Science 123  "):
        r = await client.post("/groups", json={"name": dup, "student_emails": []})
        assert r.status_code == 409
        assert "already exists" in r.json()["detail"]
    # only the original group exists
    names = [g["name"] for g in (await client.get("/groups")).json()]
    assert names.count("Computer Science 123") == 1
