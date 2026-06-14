import time
import uuid
from typing import Dict, Optional

import bcrypt
import jwt

from pathlib import Path

KEY_DIR = Path(__file__).parent / "keys"

def _load_or_generate_keys():
    priv_p = KEY_DIR / "private.pem"
    pub_p = KEY_DIR / "public.pem"
    try:
        if priv_p.exists() and pub_p.exists():
            return priv_p.read_text(), pub_p.read_text()
    except Exception:
        pass

    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend

        key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        priv = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        pub = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        return priv, pub
    except Exception:
        return "", ""


PRIVATE_KEY, PUBLIC_KEY = _load_or_generate_keys()

ACCESS_EXPIRES = 15 * 60
REFRESH_EXPIRES = 7 * 24 * 3600

USERS: Dict[str, Dict] = {}
BLACKLISTED_JTIS = set()

import os

# Random bytes hashed at startup, used only to keep bcrypt timing constant
# when the email does not exist. Never compared against real input successfully.
_DUMMY_HASH = bcrypt.hashpw(os.urandom(32), bcrypt.gensalt(rounds=12)).decode()


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def constant_time_verify(plain: str, hashed: Optional[str]) -> bool:
    """Always runs bcrypt regardless of whether the user exists."""
    target = hashed if hashed is not None else _DUMMY_HASH
    result = verify_password(plain, target)
    return result and hashed is not None


def create_access_token(subject: str, role: str, user_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "role": role,
        "uid": user_id,
        "iat": now,
        "exp": now + ACCESS_EXPIRES,
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


def create_refresh_token(subject: str, role: str, user_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "role": role,
        "uid": user_id,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + REFRESH_EXPIRES,
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


def decode_token(token: str, verify_exp: bool = True) -> Optional[Dict]:
    try:
        options = {} if verify_exp else {"verify_exp": False}
        data = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"], options=options)
        return data
    except Exception:
        return None


def blacklist_jti(jti: str):
    BLACKLISTED_JTIS.add(jti)


def is_jti_blacklisted(jti: str) -> bool:
    return jti in BLACKLISTED_JTIS