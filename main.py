from fastapi import FastAPI, Request, Form, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
import json
import os

import database
import auth
from models import TIMEPOINTS, TIMEPOINT_LABELS

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    SessionMiddleware,
    secret_key=auth.SECRET_KEY,
    session_cookie=auth.SESSION_COOKIE,
    max_age=auth.SESSION_MAX_AGE,
    same_site="lax",
    https_only=auth.is_cookie_secure(),
)


def static_v(filename: str) -> str:
    """静的ファイルの更新時刻をクエリパラメータとして返す"""
    path = os.path.join("static", filename)
    try:
        mtime = int(os.path.getmtime(path))
    except OSError:
        mtime = 0
    return f"/static/{filename}?v={mtime}"


templates.env.globals["static_v"] = static_v

# ---- OGP / SNS 共有設定 ----
# 本番環境では APP_BASE_URL=https://yourdomain.com を設定すること
APP_BASE_URL = os.environ.get("APP_BASE_URL", "").rstrip("/")

_OGP_DEFAULTS = {
    "og_site_name":    "SymptoPort",
    "og_title":        "SymptoPort — からだの天気図",
    "og_description":  "めまい・倦怠感・痛みなど、波のある症状を毎日スコアで記録。通院時に客観的なデータとして活用できます。",
    "og_image":        f"{APP_BASE_URL}/static/og-image.png",
    "og_image_app":    f"{APP_BASE_URL}/static/og-image-app.png",
    "og_locale":       "ja_JP",
    "base_url":        APP_BASE_URL,
}

templates.env.globals.update(_OGP_DEFAULTS)


def _to_weekday(date_str: str) -> int:
    """ISO日付文字列から曜日番号(0=月〜6=日)を返す Jinja2 フィルター"""
    from datetime import date as date_type
    try:
        return date_type.fromisoformat(date_str).weekday()
    except ValueError:
        return 0


templates.env.filters["to_weekday"] = _to_weekday


def get_turnstile_site_key() -> str:
    """開発環境であれば、未設定・プレースホルダーの場合にテスト用ダミーキーを返す"""
    site_key = os.environ.get("TURNSTILE_SITE_KEY", "")
    if site_key:
        site_key = site_key.strip().strip('"\'')
    is_dummy_or_empty = (
        not site_key 
        or site_key == "" 
        or "あなたの" in site_key
    )
    if is_dummy_or_empty:
        if os.environ.get("ENV") != "production":
            return "1x00000000000000000000AA"  # 常にパスするダミーサイトキー
        return ""
    return site_key


database.init_db()


@app.get("/lp", response_class=HTMLResponse)
async def lp_page(request: Request):
    """ランディングページ（OGP タグを動的に埋め込む）"""
    return templates.TemplateResponse("lp.html", {"request": request})


@app.get("/sw.js")
async def service_worker():
    """Service Worker をルートスコープ（/）で配信する"""
    from fastapi.responses import FileResponse
    return FileResponse(
        "static/sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})


@app.get("/print", response_class=HTMLResponse)
async def print_page(
    request: Request,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user_id: int = Depends(auth.get_current_user_id),
):
    from datetime import date as date_type, timedelta

    today = date_type.today()
    today_str = today.isoformat()

    # デフォルト: 直近30日
    if not to_date:
        to_date = today_str
    if not from_date:
        from_date = (today - timedelta(days=29)).isoformat()

    # バリデーション
    try:
        from_dt = date_type.fromisoformat(from_date)
        to_dt = date_type.fromisoformat(to_date)
    except ValueError:
        from_dt = today - timedelta(days=29)
        to_dt = today
        from_date, to_date = from_dt.isoformat(), to_dt.isoformat()

    # 範囲を最大90日に制限
    if (to_dt - from_dt).days > 89:
        from_dt = to_dt - timedelta(days=89)
        from_date = from_dt.isoformat()

    if from_dt > to_dt:
        from_dt, to_dt = to_dt, from_dt
        from_date, to_date = to_date, from_date

    # データ取得
    symptoms = database.get_active_symptoms(user_id)
    records_by_date = database.get_records_for_range(user_id, from_date, to_date)
    notes_by_date = database.get_notes_for_range(user_id, from_date, to_date)

    # 記録がある日付 + 範囲内の全日付を列挙（記録がない日も表示）
    dates = []
    cur = from_dt
    while cur <= to_dt:
        dates.append(cur.isoformat())
        cur += timedelta(days=1)
    # 記録が1件もない日は省く（すっきり表示のため）
    dates = [d for d in dates if d in records_by_date or d in notes_by_date]

    user = database.get_user_by_username_by_id(user_id)
    username = user["username"] if user else ""

    return templates.TemplateResponse(
        "print.html",
        {
            "request": request,
            "username": username,
            "from_date": from_date,
            "to_date": to_date,
            "today": today_str,
            "symptoms": symptoms,
            "dates": dates,
            "records_by_date": records_by_date,
            "notes_by_date": notes_by_date,
            "timepoints": TIMEPOINTS,
            "timepoint_labels": TIMEPOINT_LABELS,
        },
    )


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    user_id = request.session.get("user_id")
    is_logged_in = user_id is not None
    return templates.TemplateResponse(
        "help.html",
        {"request": request, "is_logged_in": is_logged_in}
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    turnstile_site_key = get_turnstile_site_key()
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None, "turnstile_site_key": turnstile_site_key}
    )


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    cf_turnstile_response: str = Form(None, alias="cf-turnstile-response"),
):
    turnstile_site_key = get_turnstile_site_key()

    # Turnstile ボット検証
    is_valid_turnstile = auth.verify_turnstile(cf_turnstile_response)
    print(f"[DEBUG] Turnstile verification result: {is_valid_turnstile} (response: {cf_turnstile_response[:20] if cf_turnstile_response else None}...)")

    if not is_valid_turnstile:
        print("[DEBUG] Login failed: Turnstile verification failed.")
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "ボットチェックの検証に失敗しました。リロードしてお試しください。",
                "turnstile_site_key": turnstile_site_key
            },
            status_code=400,
        )

    user = database.get_user_by_username(username)
    if not user:
        print(f"[DEBUG] Login failed: User '{username}' not found in database.")
    elif not auth.verify_password(password, user["password_hash"]):
        print(f"[DEBUG] Login failed: Incorrect password for user '{username}'.")
    else:
        print(f"[DEBUG] Login successful for user '{username}'. Session user_id set to {user['id']}.")

    if not user or not auth.verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "ユーザー名またはパスワードが違います",
                "turnstile_site_key": turnstile_site_key
            },
            status_code=400,
        )
    request.session["user_id"] = user["id"]
    return RedirectResponse(url="/", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    turnstile_site_key = get_turnstile_site_key()
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request, 
            "error": None, 
            "turnstile_site_key": turnstile_site_key,
            "default_symptoms": database._DEFAULT_SYMPTOMS
        }
    )


@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    symptoms: list[str] = Form(default=[]),
    cf_turnstile_response: str = Form(None, alias="cf-turnstile-response"),
):
    turnstile_site_key = get_turnstile_site_key()

    # バリデーション
    username = username.strip()
    if not username or not password:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "ユーザー名とパスワードを入力してください",
                "turnstile_site_key": turnstile_site_key,
                "default_symptoms": database._DEFAULT_SYMPTOMS
            },
            status_code=400,
        )

    # Turnstile ボット検証
    is_valid_turnstile = auth.verify_turnstile(cf_turnstile_response)
    print(f"[DEBUG] [Register] Turnstile verification result: {is_valid_turnstile} (response: {cf_turnstile_response[:20] if cf_turnstile_response else None}...)")

    if not is_valid_turnstile:
        print("[DEBUG] [Register] Registration failed: Turnstile verification failed.")
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "ボットチェックの検証に失敗しました。リロードしてお試しください。",
                "turnstile_site_key": turnstile_site_key,
                "default_symptoms": database._DEFAULT_SYMPTOMS
            },
            status_code=400,
        )

    # ユーザー名の文字種と長さチェック（半角英数字、3〜20文字）
    import re
    if not re.match(r"^[a-zA-Z0-9_]{3,20}$", username):
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "ユーザー名は3〜20文字の半角英数字（アンダースコア含む）で入力してください",
                "turnstile_site_key": turnstile_site_key,
                "default_symptoms": database._DEFAULT_SYMPTOMS
            },
            status_code=400,
        )

    # パスワード長さ（8文字以上）
    if len(password) < 8:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "パスワードは8文字以上で入力してください",
                "turnstile_site_key": turnstile_site_key,
                "default_symptoms": database._DEFAULT_SYMPTOMS
            },
            status_code=400,
        )

    # パスワード一致チェック
    if password != password_confirm:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "パスワードが一致しません",
                "turnstile_site_key": turnstile_site_key,
                "default_symptoms": database._DEFAULT_SYMPTOMS
            },
            status_code=400,
        )

    # 重複チェック
    existing = database.get_user_by_username(username)
    if existing:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "そのユーザー名はすでに使用されています",
                "turnstile_site_key": turnstile_site_key,
                "default_symptoms": database._DEFAULT_SYMPTOMS
            },
            status_code=400,
        )

    # 新規登録
    hashed = auth.hash_password(password)
    database.create_user(username, hashed, symptoms)

    # 登録直後の自動ログイン
    user = database.get_user_by_username(username)
    request.session["user_id"] = user["id"]
    return RedirectResponse(url="/", status_code=302)


@app.get("/", response_class=HTMLResponse)
async def record_page(
    request: Request,
    date: Optional[str] = None,
):
    from datetime import date as date_type

    # 未ログインユーザーはLPへ
    user_id = request.session.get("user_id")
    if user_id is None:
        return RedirectResponse(url="/lp", status_code=302)

    # date パラメータのバリデーション
    if date:
        try:
            date_type.fromisoformat(date)
        except ValueError:
            return RedirectResponse(url="/", status_code=302)

    today = date or date_type.today().isoformat()
    existing = database.get_records_for_date(user_id, today)
    note = database.get_note(user_id, today)
    symptoms = database.get_active_symptoms(user_id)
    return templates.TemplateResponse(
        "record.html",
        {
            "request": request,
            "date": today,
            "symptoms": symptoms,
            "timepoints": TIMEPOINTS,
            "timepoint_labels": TIMEPOINT_LABELS,
            "existing": json.dumps(existing),
            "note": note,
        },
    )


@app.post("/api/save")
async def save_records(
    request: Request,
    user_id: int = Depends(auth.get_current_user_id),
):
    from datetime import date as date_type
    body = await request.json()
    date = body.get("date")
    entries = body.get("entries", [])
    note = body.get("note", "")

    # date パラメータのバリデーション
    if date:
        try:
            date_type.fromisoformat(date)
        except ValueError:
            return JSONResponse({"error": "invalid date format"}, status_code=400)

    # note の長さを最大2000文字に制限（ストレージ枯渇対策）
    note = note[:2000]

    valid_symptoms = {s["name"] for s in database.get_active_symptoms(user_id)}

    for entry in entries:
        symptom = entry.get("symptom")
        timepoint = entry.get("timepoint")
        score = entry.get("score")

        if symptom not in valid_symptoms or timepoint not in TIMEPOINTS:
            return JSONResponse({"error": "invalid data"}, status_code=400)
        if score is not None and score not in range(-1, 6):
            return JSONResponse({"error": "invalid score"}, status_code=400)

        database.upsert_record(user_id, date, symptom, timepoint, score)

    database.upsert_note(user_id, date, note)
    return JSONResponse({"ok": True})


@app.get("/api/records")
async def get_records(
    date: str,
    user_id: int = Depends(auth.get_current_user_id),
):
    from datetime import date as date_type
    try:
        date_type.fromisoformat(date)
    except ValueError:
        return JSONResponse({"error": "invalid date format"}, status_code=400)

    return JSONResponse({
        "records": database.get_records_for_date(user_id, date),
        "note": database.get_note(user_id, date),
    })


# ---- 症状管理 ----

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user_id: int = Depends(auth.get_current_user_id),
):
    symptoms = database.get_all_symptoms(user_id)
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "symptoms": symptoms},
    )


@app.post("/settings/add")
async def add_symptom(
    name: str = Form(...),
    label: str = Form(...),
    use_timepoints: int = Form(1),
    is_reverse: int = Form(0),
    user_id: int = Depends(auth.get_current_user_id),
):
    ok = database.add_symptom(user_id, name.strip(), label.strip(), use_timepoints, is_reverse)
    if not ok:
        return RedirectResponse(url="/settings?error=duplicate", status_code=302)
    return RedirectResponse(url="/settings", status_code=302)


@app.post("/settings/update/{symptom_id}")
async def update_symptom(
    symptom_id: int,
    label: str = Form(...),
    use_timepoints: int = Form(1),
    active: int = Form(1),
    is_reverse: int = Form(0),
    user_id: int = Depends(auth.get_current_user_id),
):
    database.update_symptom(user_id, symptom_id, label.strip(), use_timepoints, active, is_reverse)
    return RedirectResponse(url="/settings", status_code=302)


@app.post("/settings/reorder")
async def reorder_symptoms(
    request: Request,
    user_id: int = Depends(auth.get_current_user_id),
):
    body = await request.json()
    ordered_ids = body.get("ids", [])
    if len(ordered_ids) > 100:
        return JSONResponse({"error": "too many symptoms"}, status_code=400)
    database.reorder_symptoms(user_id, ordered_ids)
    return JSONResponse({"ok": True})


@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc):
    return RedirectResponse(url="/login", status_code=302)
