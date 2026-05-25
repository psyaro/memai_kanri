from fastapi import FastAPI, Request, Form, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
import json
import os

import database
import auth
from models import TIMEPOINTS, TIMEPOINT_LABELS

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


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
    username: str = Form(...),
    password: str = Form(...),
):
    user = database.get_user_by_username(username)
    if not user or not auth.verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {"request": {}, "error": "ユーザー名またはパスワードが違います"},
            status_code=400,
        )
    token = auth.create_session_token(user["id"])
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


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
    symptoms = database.get_active_symptoms()
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

    valid_symptoms = {s["name"] for s in database.get_active_symptoms()}

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
    symptoms = database.get_all_symptoms()
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
    ok = database.add_symptom(name.strip(), label.strip(), use_timepoints)
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
    database.update_symptom(symptom_id, label.strip(), use_timepoints, active)
    return RedirectResponse(url="/settings", status_code=302)


@app.post("/settings/reorder")
async def reorder_symptoms(
    request: Request,
    user_id: int = Depends(auth.get_current_user_id),
):
    body = await request.json()
    database.reorder_symptoms(body.get("ids", []))
    return JSONResponse({"ok": True})


@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc):
    return RedirectResponse(url="/login", status_code=302)
