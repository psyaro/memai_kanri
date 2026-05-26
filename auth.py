import hashlib
import hmac
import os
import base64
from fastapi import Request, HTTPException
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
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def is_cookie_secure() -> bool:
    """本番環境(ENV=production)の場合はCookieにSecure属性を付与する"""
    return os.environ.get("ENV") == "production"


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


def get_current_user_id(request: Request) -> int:
    """SessionMiddlewareからユーザーIDを取得する依存注入用ヘルパー"""
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


import urllib.request
import urllib.parse
import json

def verify_turnstile(token: str) -> bool:
    """Cloudflare Turnstile トークンの正当性を検証する"""
    is_production = os.environ.get("ENV") == "production"

    # 開発環境 (ENV != production) の場合は、検証を常に自動パスさせてローカル開発を円滑にする
    if not is_production:
        print("[DEBUG] Development mode: Automatically passing Turnstile verification.")
        return True

    # --- 以下は本番環境 (production) のみの厳格な検証処理 ---
    secret_key = os.environ.get("TURNSTILE_SECRET_KEY")
    if secret_key:
        secret_key = secret_key.strip().strip('"\'')

    # 本番環境でシークレットキーが未設定、プレースホルダー、またはテスト用ダミーキーの場合は即座に拒否
    is_invalid_for_prod = (
        not secret_key 
        or secret_key == "" 
        or "あなたの" in secret_key 
        or secret_key.startswith("1x0000000")  # テスト用ダミーキーのブロック
    )

    if is_invalid_for_prod:
        print("[ERROR] Production Mode: Invalid or missing TURNSTILE_SECRET_KEY!", file=sys.stderr)
        return False

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
        print(f"[ERROR] Production Turnstile verification failed: {e}", file=sys.stderr)
        return False



