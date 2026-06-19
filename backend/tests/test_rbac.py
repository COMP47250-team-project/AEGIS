"""RBAC tests for require_role (AEGIS-27).

Covers every role combination against a professor endpoint (GET /exams) and a
student endpoint (GET /student/sessions), plus missing/expired/bad-signature
JWTs. The `client` fixture is requested so its get_db override stays active.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.main import app

PROFESSOR_ENDPOINT = "/exams"
STUDENT_ENDPOINT = "/student/sessions"


def _make_token(
    sub: str,
    role: str | None = None,
    *,
    secret: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    payload: dict = {"sub": sub}
    if role is not None:
        payload["role"] = role
    if expires_delta is not None:
        payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        payload,
        secret or settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _client(token: str | None) -> AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Allowed combinations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_professor_allowed_on_professor_endpoint(client: AsyncClient) -> None:
    # `client` fixture carries a professor token.
    resp = await client.get(PROFESSOR_ENDPOINT)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_student_allowed_on_student_endpoint(client: AsyncClient) -> None:
    token = _make_token("stud-rbac", "student")
    async with _client(token) as student:
        resp = await student.get(STUDENT_ENDPOINT)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cross-role -> 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_forbidden_on_professor_endpoint(client: AsyncClient) -> None:
    token = _make_token("stud-rbac", "student")
    async with _client(token) as student:
        resp = await student.get(PROFESSOR_ENDPOINT)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_professor_forbidden_on_student_endpoint(client: AsyncClient) -> None:
    # Professor token hitting a student-only route.
    resp = await client.get(STUDENT_ENDPOINT)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Unauthenticated -> 401 (on both endpoint families)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", [PROFESSOR_ENDPOINT, STUDENT_ENDPOINT])
async def test_missing_jwt_returns_401(client: AsyncClient, endpoint: str) -> None:
    async with _client(None) as anon:
        resp = await anon.get(endpoint)
    assert resp.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["professor", "student"])
async def test_expired_jwt_returns_401(client: AsyncClient, role: str) -> None:
    endpoint = PROFESSOR_ENDPOINT if role == "professor" else STUDENT_ENDPOINT
    token = _make_token("exp-rbac", role, expires_delta=timedelta(hours=-1))
    async with _client(token) as expired:
        resp = await expired.get(endpoint)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_bad_signature_returns_401(client: AsyncClient) -> None:
    token = _make_token("forged", "professor", secret="not-the-real-secret-key")
    async with _client(token) as forged:
        resp = await forged.get(PROFESSOR_ENDPOINT)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_without_role_claim_is_forbidden(client: AsyncClient) -> None:
    # Validly-signed token with no role claim must not pass a role gate.
    token = _make_token("no-role", role=None)
    async with _client(token) as no_role:
        resp = await no_role.get(PROFESSOR_ENDPOINT)
    assert resp.status_code == 403
