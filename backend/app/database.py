from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Lazy-initialized engine and session factory. In CI we create many TestClient
# instances concurrently; creating the engine at module import time can cause
# incidental connection attempts to the default PostgreSQL URL. Make the
# engine/sessionmaker initialise on first use instead.
_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def _ensure_engine() -> None:
    """Create the SQLAlchemy async engine and sessionmaker on first use."""
    global _engine, _AsyncSessionLocal
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url, echo=settings.app_env == "development"
        )
        _AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class _SessionFactory:
    """Callable proxy that ensures the sessionmaker is initialised."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        _ensure_engine()
        assert _AsyncSessionLocal is not None, "SessionLocal must be initialized"
        return _AsyncSessionLocal(*args, **kwargs)


# Exported symbol that mimics the async_sessionmaker interface: use
# `async with AsyncSessionLocal() as session` as before.
AsyncSessionLocal = _SessionFactory()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _ensure_engine()
    assert _AsyncSessionLocal is not None, "SessionLocal must be initialized"
    async with _AsyncSessionLocal() as session:
        yield session
