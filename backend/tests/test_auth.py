# tests for JWT auth endpoints - June 2026
import pytest
from fastapi.testclient import TestClient
from auth.main import app

client = TestClient(app)

TEST_PWD = "SecurePass123"
WRONG_PWD = "wrongpassword"
ANY_PWD = "anything"

VALID_USER = {
    "email": "testuser@example.com",
    "password": TEST_PWD,
    "role": "user",
    "full_name": "Test User",
}


@pytest.fixture(autouse=True)
def clear_store():
    from auth import auth
    auth.USERS.clear()
    auth.BLACKLISTED_JTIS.clear()


def register_and_login():
    client.post("/auth/register", json=VALID_USER)
    res = client.post("/auth/login", json={
        "email": VALID_USER["email"],
        "password": TEST_PWD,
    })
    return res.json()


# Register
def test_register_returns_201_with_tokens():
    res = client.post("/auth/register", json=VALID_USER)
    assert res.status_code == 201
    body = res.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_register_duplicate_email_returns_409():
    client.post("/auth/register", json=VALID_USER)
    res = client.post("/auth/register", json=VALID_USER)
    assert res.status_code == 409


# Login
def test_login_returns_200_with_tokens():
    client.post("/auth/register", json=VALID_USER)
    res = client.post("/auth/login", json={
        "email": VALID_USER["email"],
        "password": TEST_PWD,
    })
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_login_wrong_password_returns_401():
    client.post("/auth/register", json=VALID_USER)
    res = client.post("/auth/login", json={
        "email": VALID_USER["email"],
        "password": WRONG_PWD,
    })
    assert res.status_code == 401


def test_login_nonexistent_email_returns_401():
    res = client.post("/auth/login", json={
        "email": "ghost@example.com",
        "password": ANY_PWD,
    })
    assert res.status_code == 401


def test_login_wrong_password_and_nonexistent_email_same_message():
    client.post("/auth/register", json=VALID_USER)

    wrong_pass = client.post("/auth/login", json={
        "email": VALID_USER["email"],
        "password": WRONG_PWD,
    })
    ghost = client.post("/auth/login", json={
        "email": "ghost@example.com",
        "password": ANY_PWD,
    })

    assert wrong_pass.json()["detail"] == ghost.json()["detail"]


# Refresh
def test_refresh_returns_new_access_token():
    tokens = register_and_login()
    res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_refresh_with_invalid_token_returns_401():
    res = client.post("/auth/refresh", json={"refresh_token": "notavalidtoken"})
    assert res.status_code == 401


def test_refresh_with_blacklisted_token_returns_401():
    tokens = register_and_login()
    client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 401


# Logout
def test_logout_returns_200():
    tokens = register_and_login()
    res = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 200


# Protected route
def test_protected_route_with_valid_token_returns_200():
    tokens = register_and_login()
    res = client.get("/protected", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert res.status_code == 200


def test_protected_route_with_no_token_returns_401():
    res = client.get("/protected")
    assert res.status_code == 401


def test_protected_route_with_invalid_token_returns_401():
    res = client.get("/protected", headers={"Authorization": "Bearer invalidtoken"})
    assert res.status_code == 401


# Full flow from acceptance criteria
def test_register_login_protected_flow():
    reg = client.post("/auth/register", json=VALID_USER)
    assert reg.status_code == 201

    login = client.post("/auth/login", json={
        "email": VALID_USER["email"],
        "password": TEST_PWD,
    })
    assert login.status_code == 200

    token = login.json()["access_token"]
    protected = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert protected.status_code == 200
