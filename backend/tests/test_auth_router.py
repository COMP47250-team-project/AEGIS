# Tests for the DB-backed /auth/* endpoints in app/routers/auth.py
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app


def _student(**overrides):
    uid = uuid.uuid4().hex[:8]
    return {"email": f"student-{uid}@ucd.ie", "password": "SecurePass1", "role": "student", "name": "Alice", **overrides}


def _professor(**overrides):
    uid = uuid.uuid4().hex[:8]
    return {"email": f"prof-{uid}@ucd.ie", "password": "ProfPass123", "role": "professor", "name": "Dr. Bob", **overrides}


@pytest_asyncio.fixture
async def anon_client(db_session):
    """Unauthenticated client — no Authorization header."""
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

async def test_register_student_returns_201_with_tokens_and_user(anon_client):
    payload = _student()
    res = await anon_client.post("/auth/register", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["email"] == payload["email"]
    assert body["user"]["role"] == "student"
    assert body["user"]["name"] == "Alice"


async def test_register_professor_returns_201_with_correct_role(anon_client):
    res = await anon_client.post("/auth/register", json=_professor())
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "professor"


async def test_register_duplicate_email_returns_409(anon_client):
    payload = _student()
    await anon_client.post("/auth/register", json=payload)
    res = await anon_client.post("/auth/register", json=payload)
    assert res.status_code == 409


async def test_register_without_name_is_allowed(anon_client):
    res = await anon_client.post("/auth/register", json=_student(name=None))
    assert res.status_code == 201
    assert res.json()["user"]["name"] is None


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def test_login_returns_200_with_tokens_and_user(anon_client):
    payload = _student()
    await anon_client.post("/auth/register", json=payload)
    res = await anon_client.post("/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["email"] == payload["email"]


async def test_login_wrong_password_returns_401(anon_client):
    payload = _student()
    await anon_client.post("/auth/register", json=payload)
    res = await anon_client.post("/auth/login", json={"email": payload["email"], "password": "wrongpassword"})
    assert res.status_code == 401


async def test_login_nonexistent_email_returns_401(anon_client):
    res = await anon_client.post("/auth/login", json={"email": "ghost@ucd.ie", "password": "doesnotmatter"})
    assert res.status_code == 401


async def test_login_errors_have_same_message_for_wrong_password_and_missing_user(anon_client):
    """Prevents user enumeration via different error messages."""
    payload = _student()
    await anon_client.post("/auth/register", json=payload)
    wrong_pw = await anon_client.post("/auth/login", json={"email": payload["email"], "password": "wrongpassword"})
    missing = await anon_client.post("/auth/login", json={"email": "ghost2@ucd.ie", "password": "wrongpassword"})
    assert wrong_pw.json()["detail"] == missing.json()["detail"]


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

async def test_refresh_returns_new_access_token(anon_client):
    reg = await anon_client.post("/auth/register", json=_student())
    refresh_token = reg.json()["refresh_token"]
    res = await anon_client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 200
    assert "access_token" in res.json()


async def test_refresh_with_invalid_token_returns_401(anon_client):
    res = await anon_client.post("/auth/refresh", json={"refresh_token": "notavalidtoken"})
    assert res.status_code == 401


async def test_refresh_with_revoked_token_returns_401(anon_client):
    reg = await anon_client.post("/auth/register", json=_student())
    refresh_token = reg.json()["refresh_token"]
    await anon_client.post("/auth/logout", json={"refresh_token": refresh_token})
    res = await anon_client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

async def test_logout_returns_200(anon_client):
    reg = await anon_client.post("/auth/register", json=_student())
    refresh_token = reg.json()["refresh_token"]
    res = await anon_client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Tokens work on protected routes
# ---------------------------------------------------------------------------

async def test_access_token_authorises_protected_routes(anon_client):
    reg = await anon_client.post("/auth/register", json=_professor())
    access = reg.json()["access_token"]
    res = await anon_client.get("/quizzes", headers={"Authorization": f"Bearer {access}"})
    assert res.status_code == 200
