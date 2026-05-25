import hashlib
import hmac
import os
import base64
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Cookie, HTTPException
from typing import Optional

SECRET_KEY = "change-this-secret-key-in-production"
SESSION_COOKIE = "session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

_serializer = URLSafeTimedSerializer(SECRET_KEY)

_ITERATIONS = 260000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return base64.b64encode(salt + dk).decode()


def verify_password(password: str, stored: str) -> bool:
    raw = base64.b64decode(stored.encode())
    salt, dk = raw[:16], raw[16:]
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(dk, candidate)


def create_session_token(user_id: int) -> str:
    return _serializer.dumps({"user_id": user_id})


def decode_session_token(token: str) -> Optional[int]:
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data["user_id"]
    except (BadSignature, SignatureExpired):
        return None


def get_current_user_id(session: Optional[str] = Cookie(default=None)) -> int:
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = decode_session_token(session)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user_id
