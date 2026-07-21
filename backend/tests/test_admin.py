"""AEGIS-107 — super-admin console: RBAC, listing, audit log, deactivate."""

import uuid

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.audit import AuditLog
from app.models.user import User
from app.services.audit import (
    EXAM_CREATED,
    STUDENT_FLAGGED,
    USER_REGISTERED,
)


def _headers(role: str, user_id: str = "admin-1") -> dict[str, str]:
    token = jwt.encode(
        {"sub": user_id, "role": role},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


ADMIN = _headers("super_admin")


@pytest.mark.asyncio
async def test_non_admin_forbidden(client: AsyncClient):
    for role in ("professor", "student"):
        for path in ("/admin/users", "/admin/exams", "/admin/audit"):
            resp = await client.get(path, headers=_headers(role))
            assert resp.status_code == 403, (role, path)


@pytest.mark.asyncio
async def test_list_users_with_role_filter_and_pagination(
    client: AsyncClient, db_session: AsyncSession
):
    for i in range(3):
        db_session.add(
            User(email=f"stud{i}@x.ie", hashed_password="x", role="student")
        )
    db_session.add(User(email="prof@x.ie", hashed_password="x", role="professor"))
    await db_session.commit()

    resp = await client.get("/admin/users?role=student", headers=ADMIN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 3
    assert all(u["role"] == "student" for u in body["items"])

    paged = await client.get("/admin/users?limit=2&offset=0", headers=ADMIN)
    assert paged.status_code == 200
    assert len(paged.json()["items"]) == 2


@pytest.mark.asyncio
async def test_audit_captures_event_types(
    client: AsyncClient, db_session: AsyncSession
):
    # user_registered fires end-to-end via the register endpoint.
    reg = await client.post(
        "/auth/register",
        json={"email": "newuser@x.ie", "password": "pw12345678", "role": "student"},
    )
    assert reg.status_code == 201

    # exam_created + student_flagged inserted directly to assert the log surfaces them.
    db_session.add(
        AuditLog(event_type=EXAM_CREATED, actor_id="prof-1", target_id="exam-1")
    )
    db_session.add(
        AuditLog(
            event_type=STUDENT_FLAGGED,
            target_id="stud-9",
            audit_metadata={"risk_score": 0.9},
        )
    )
    await db_session.commit()

    resp = await client.get("/admin/audit", headers=ADMIN)
    assert resp.status_code == 200
    seen = {e["event_type"] for e in resp.json()["items"]}
    assert {USER_REGISTERED, EXAM_CREATED, STUDENT_FLAGGED} <= seen


@pytest.mark.asyncio
async def test_deactivate_user(client: AsyncClient, db_session: AsyncSession):
    user = User(email="target@x.ie", hashed_password="x", role="student")
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(f"/admin/users/{user.id}/deactivate", headers=ADMIN)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    missing = await client.post(
        f"/admin/users/{uuid.uuid4()}/deactivate", headers=ADMIN
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_deactivated_user_login_rejected_and_reactivated_login_succeeds(
    client: AsyncClient,
):
    email, password = "deactivated@x.ie", "pw12345678"
    reg = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "role": "student"},
    )
    user_id = reg.json()["user"]["id"]

    deactivate = await client.post(
        f"/admin/users/{user_id}/deactivate", headers=ADMIN
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    blocked = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert blocked.status_code == 403
    assert (
        blocked.json()["detail"]
        == "Your account has been deactivated. Please contact the support team for assistance."
    )

    activate = await client.post(f"/admin/users/{user_id}/activate", headers=ADMIN)
    assert activate.status_code == 200
    assert activate.json()["is_active"] is True

    allowed = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_login_sets_last_login(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "ll@x.ie", "password": "pw12345678", "role": "student"},
    )
    await client.post("/auth/login", json={"email": "ll@x.ie", "password": "pw12345678"})

    resp = await client.get("/admin/users?role=student", headers=ADMIN)
    row = next(u for u in resp.json()["items"] if u["email"] == "ll@x.ie")
    assert row["last_login"] is not None
