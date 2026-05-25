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

database.init_db()


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = database.get_user_by_username(username)
    if not user or not auth.verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "ユーザー名またはパスワードが違います"},
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
    turnstile_site_key = os.environ.get("TURNSTILE_SITE_KEY", "")
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "error": None, "turnstile_site_key": turnstile_site_key}
    )


@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    cf_turnstile_response: str = Form(None, alias="cf-turnstile-response"),
):
    turnstile_site_key = os.environ.get("TURNSTILE_SITE_KEY", "")

    # バリデーション
    username = username.strip()
    if not username or not password:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "ユーザー名とパスワードを入力してください",
                "turnstile_site_key": turnstile_site_key
            },
            status_code=400,
        )

    # Turnstile ボット検証
    if not auth.verify_turnstile(cf_turnstile_response):
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "ボットチェックの検証に失敗しました。リロードしてお試しください。",
                "turnstile_site_key": turnstile_site_key
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
                "turnstile_site_key": turnstile_site_key
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
                "turnstile_site_key": turnstile_site_key
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
                "turnstile_site_key": turnstile_site_key
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
                "turnstile_site_key": turnstile_site_key
            },
            status_code=400,
        )

    # 新規登録
    hashed = auth.hash_password(password)
    database.create_user(username, hashed)

    # 登録直後の自動ログイン
    user = database.get_user_by_username(username)
    request.session["user_id"] = user["id"]
    return RedirectResponse(url="/", status_code=302)


@app.get("/", response_class=HTMLResponse)
async def record_page(
    request: Request,
    date: Optional[str] = None,
    user_id: int = Depends(auth.get_current_user_id),
):
    from datetime import date as date_type
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
    body = await request.json()
    date = body.get("date")
    entries = body.get("entries", [])
    note = body.get("note", "")

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
    user_id: int = Depends(auth.get_current_user_id),
):
    ok = database.add_symptom(user_id, name.strip(), label.strip(), use_timepoints)
    if not ok:
        return RedirectResponse(url="/settings?error=duplicate", status_code=302)
    return RedirectResponse(url="/settings", status_code=302)


@app.post("/settings/update/{symptom_id}")
async def update_symptom(
    symptom_id: int,
    label: str = Form(...),
    use_timepoints: int = Form(1),
    active: int = Form(1),
    user_id: int = Depends(auth.get_current_user_id),
):
    database.update_symptom(user_id, symptom_id, label.strip(), use_timepoints, active)
    return RedirectResponse(url="/settings", status_code=302)


@app.post("/settings/reorder")
async def reorder_symptoms(
    request: Request,
    user_id: int = Depends(auth.get_current_user_id),
):
    body = await request.json()
    database.reorder_symptoms(user_id, body.get("ids", []))
    return JSONResponse({"ok": True})


@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc):
    return RedirectResponse(url="/login", status_code=302)
