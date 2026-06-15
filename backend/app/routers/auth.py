"""Authentication endpoints — register, login, refresh, logout.

Backed by PostgreSQL via SQLAlchemy; uses HS256 JWT (same key as dependencies.py).
Tokens generated here are accepted by all other protected routes.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory revocation set for refresh tokens (survives process lifetime).
# For production, move to Redis or a DB table.
_REVOKED_JTIS: set[str] = set()

# Dummy hash used in constant-time password check when user doesn't exist.
_DUMMY_HASH = bcrypt.hashpw(os.urandom(32), bcrypt.gensalt(rounds=12)).decode()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class UserRead(BaseModel):
    id: str
    email: str
    role: str
    name: str | None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    role: Literal["student", "professor"] = "student"
    name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _make_jwt(
    user_id: str,
    role: str,
    expires_delta: timedelta,
    include_jti: bool = False,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + expires_delta,
    }
    if include_jti:
        payload["jti"] = str(uuid.uuid4())
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def _build_response(user: User) -> TokenResponse:
    uid = str(user.id)
    access = _make_jwt(uid, user.role, timedelta(minutes=settings.jwt_expire_minutes))
    refresh = _make_jwt(uid, user.role, timedelta(days=7), include_jti=True)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserRead(id=uid, email=user.email, role=user.role, name=user.full_name),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterIn,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=_hash_password(payload.password),
        role=payload.role,
        full_name=payload.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _build_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginIn,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Always run bcrypt to prevent timing-based user enumeration.
    candidate_hash = user.hashed_password if user else _DUMMY_HASH
    is_valid = _verify_password(payload.password, candidate_hash)

    if not is_valid or user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return _build_response(user)


@router.post("/refresh")
async def refresh(body: RefreshIn) -> dict:
    data = _decode_jwt(body.refresh_token)
    if data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    jti = data.get("jti")
    if jti and jti in _REVOKED_JTIS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    access = _make_jwt(
        data["sub"],
        data.get("role", "student"),
        timedelta(minutes=settings.jwt_expire_minutes),
    )
    return {"access_token": access}


@router.post("/logout")
async def logout(body: LogoutIn) -> dict:
    data = _decode_jwt(body.refresh_token)
    if data:
        jti = data.get("jti")
        if jti:
            _REVOKED_JTIS.add(jti)
    return {"message": "Logged out"}
