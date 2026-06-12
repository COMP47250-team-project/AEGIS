<<<<<<< HEAD
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.app_env == "development")

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
=======
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker
from .config import settings
>>>>>>> 76fb0a1 (Fix SQLAlchemy + Database URL)


class Base(DeclarativeBase):
    pass


<<<<<<< HEAD
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
=======
Base = DeclarativeBase()
>>>>>>> 76fb0a1 (Fix SQLAlchemy + Database URL)
