"""Shared FastAPI dependencies."""

from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

_bearer = HTTPBearer()

# auto_error=False so a missing header yields 401, not HTTPBearer's default 403.
_bearer_optional = HTTPBearer(auto_error=False)

_INVALID_TOKEN = "Invalid token"


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Validate Bearer JWT and return the subject (user id)."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_TOKEN
            )
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_TOKEN
        )


def require_role(role: Literal["student", "professor"]):
    """Dependency factory allowing only callers whose JWT role matches `role`.

    Missing/expired/invalid token -> 401; wrong role -> 403. Returns the user id.
    """

    def _dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
    ) -> str:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_TOKEN
            )

        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_TOKEN
            )

        if payload.get("role") != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {role} role",
            )

        return user_id

    return _dependency
