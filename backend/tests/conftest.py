"""Pytest fixtures for the AEGIS backend test suite."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite engine for tests (no PostgreSQL required in CI)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_TestSessionLocal = async_sessionmaker(_test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _TestSessionLocal() as session:
        yield session


def _make_token(user_id: str = "prof-001", role: str = "professor") -> str:
    return jwt.encode(
        {"sub": user_id, "role": role},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _auth_headers(user_id: str, role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id, role)}"}


@pytest.fixture
def auth_headers_professor() -> dict[str, str]:
    """Bearer header for a professor JWT (AEGIS-68)."""
    return _auth_headers("prof-001", "professor")


@pytest.fixture
def auth_headers_student() -> dict[str, str]:
    """Bearer header for a student JWT (AEGIS-68)."""
    return _auth_headers("student-001", "student")


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    token = _make_token()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
