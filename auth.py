import hashlib
import hmac
import os
import base64
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Cookie, HTTPException
from typing import Optional

import sys

SECRET_KEY = os.environ.get("SESSION_SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("ENV") == "production":
        print("CRITICAL SECURITY ERROR: 'SESSION_SECRET_KEY' environment variable is not set in production!", file=sys.stderr)
        sys.exit(1)
    else:
        # 開発環境用フォールバック
        SECRET_KEY = "change-this-secret-key-in-production-dev-fallback"

SESSION_COOKIE = "session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

_serializer = URLSafeTimedSerializer(SECRET_KEY)


def is_cookie_secure() -> bool:
    """本番環境(ENV=production)の場合はCookieにSecure属性を付与する"""
    return os.environ.get("ENV") == "production"


import urllib.request
import urllib.parse
import json

def verify_turnstile(token: str) -> bool:
    """Cloudflare Turnstile トークンの正当性を検証する"""
    secret_key = os.environ.get("TURNSTILE_SECRET_KEY")
    if not secret_key:
        if os.environ.get("ENV") == "production":
            return False
        # 開発環境用のデバッグログ
        print("Warning: 'TURNSTILE_SECRET_KEY' is not set. Skipping Turnstile verification in development mode.")
        return True

    url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    data = urllib.parse.urlencode({
        "secret": secret_key,
        "response": token,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("success", False)
    except Exception as e:
        print(f"Turnstile verification failed: {e}", file=sys.stderr)
        return False


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
