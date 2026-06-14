from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

from . import auth

app = FastAPI()


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    role: Optional[str] = "user"
    full_name: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


def raise_401():
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/auth/register", status_code=201)
def register(payload: RegisterIn):
    if payload.email in auth.USERS:
        # Generic message to prevent confirming whether email is taken
        raise HTTPException(status_code=409, detail="Registration failed")

    user_id = str(uuid.uuid4())
    hashed = auth.hash_password(payload.password)
    auth.USERS[payload.email] = {
        "id": user_id,
        "email": payload.email,
        "password": hashed,
        "role": payload.role,
        "full_name": payload.full_name,
    }

    access = auth.create_access_token(payload.email, payload.role, user_id)
    refresh = auth.create_refresh_token(payload.email, payload.role, user_id)
    return {"access_token": access, "refresh_token": refresh}


@app.post("/auth/login")
def login(payload: LoginIn):
    user = auth.USERS.get(payload.email)
    # Always run bcrypt even when user doesn't exist to prevent timing attacks
    stored_hash = user["password"] if user else None
    if not auth.constant_time_verify(payload.password, stored_hash):
        raise_401()

    access = auth.create_access_token(user["email"], user["role"], user["id"])
    refresh = auth.create_refresh_token(user["email"], user["role"], user["id"])
    return {"access_token": access, "refresh_token": refresh}


@app.post("/auth/refresh")
def refresh(body: RefreshIn):
    data = auth.decode_token(body.refresh_token)
    if not data:
        raise_401()

    jti = data.get("jti")
    if not jti or auth.is_jti_blacklisted(jti):
        raise_401()

    # Re-use role from the refresh token payload, not hardcoded
    access = auth.create_access_token(data["sub"], data.get("role", "user"), data["uid"])
    return {"access_token": access}


@app.post("/auth/logout")
def logout(body: LogoutIn):
    # Decode without expiry check so expired tokens still get blacklisted
    data = auth.decode_token(body.refresh_token, verify_exp=False)
    if not data:
        raise_401()

    jti = data.get("jti")
    if jti:
        auth.blacklist_jti(jti)

    return {"message": "Logged out successfully"}


def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    data = auth.decode_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return data


@app.get("/protected")
def protected(user=Depends(get_current_user)):
    return {"status": "ok", "user": user.get("sub")}