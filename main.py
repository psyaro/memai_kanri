from fastapi import FastAPI, Request, Form, Depends, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

import database
import auth
from models import TIMEPOINTS, TIMEPOINT_LABELS

CITIES = {
    "kushiro": {"name": "北海道 (釧路)", "lat": 42.9849, "lon": 144.3818},
    "sapporo": {"name": "北海道 (札幌)", "lat": 43.0618, "lon": 141.3545},
    "aomori": {"name": "青森県 (青森)", "lat": 40.8224, "lon": 140.7473},
    "morioka": {"name": "岩手県 (盛岡)", "lat": 39.7020, "lon": 141.1544},
    "sendai": {"name": "宮城県 (仙台)", "lat": 38.2682, "lon": 140.8694},
    "akita": {"name": "秋田県 (秋田)", "lat": 39.7198, "lon": 140.1023},
    "yamagata": {"name": "山形県 (山形)", "lat": 38.2554, "lon": 140.3396},
    "fukushima": {"name": "福島県 (福島)", "lat": 37.7608, "lon": 140.4747},
    "mito": {"name": "茨城県 (水戸)", "lat": 36.3659, "lon": 140.4711},
    "utsunomiya": {"name": "栃木県 (宇都宮)", "lat": 36.5551, "lon": 139.8826},
    "maebashi": {"name": "群馬県 (前橋)", "lat": 36.3895, "lon": 139.0634},
    "saitama": {"name": "埼玉県 (さいたま)", "lat": 35.8617, "lon": 139.6455},
    "chiba": {"name": "千葉県 (千葉)", "lat": 35.6073, "lon": 140.1063},
    "tokyo": {"name": "東京都 (東京)", "lat": 35.6895, "lon": 139.6917},
    "yokohama": {"name": "神奈川県 (横浜)", "lat": 35.4437, "lon": 139.6380},
    "niigata": {"name": "新潟県 (新潟)", "lat": 37.9162, "lon": 139.0364},
    "toyama": {"name": "富山県 (富山)", "lat": 36.6953, "lon": 137.2113},
    "kanazawa": {"name": "石川県 (金沢)", "lat": 36.5613, "lon": 136.6562},
    "fukui": {"name": "福井県 (福井)", "lat": 36.0641, "lon": 136.2196},
    "kofu": {"name": "山梨県 (甲府)", "lat": 35.6622, "lon": 138.5683},
    "nagano": {"name": "長野県 (長野)", "lat": 36.6513, "lon": 138.1810},
    "gifu": {"name": "岐阜県 (岐阜)", "lat": 35.4233, "lon": 136.7607},
    "shizuoka": {"name": "静岡県 (静岡)", "lat": 34.9756, "lon": 138.3828},
    "nagoya": {"name": "愛知県 (名古屋)", "lat": 35.1815, "lon": 136.9064},
    "tsu": {"name": "三重県 (津)", "lat": 34.7186, "lon": 136.5052},
    "otsu": {"name": "滋賀県 (大津)", "lat": 35.0178, "lon": 135.8547},
    "kyoto": {"name": "京都府 (京都)", "lat": 35.0116, "lon": 135.7681},
    "osaka": {"name": "大阪府 (大阪)", "lat": 34.6937, "lon": 135.5023},
    "kobe": {"name": "兵庫県 (神戸)", "lat": 34.6901, "lon": 135.1955},
    "nara": {"name": "奈良県 (奈良)", "lat": 34.6851, "lon": 135.8048},
    "wakayama": {"name": "和歌山県 (和歌山)", "lat": 34.2300, "lon": 135.1708},
    "tottori": {"name": "鳥取県 (鳥取)", "lat": 35.5011, "lon": 134.2351},
    "matsue": {"name": "島根県 (松江)", "lat": 35.4681, "lon": 133.0484},
    "okayama": {"name": "岡山県 (岡山)", "lat": 34.6551, "lon": 133.9181},
    "hiroshima": {"name": "広島県 (広島)", "lat": 34.3853, "lon": 132.4553},
    "yamaguchi": {"name": "山口県 (山口)", "lat": 34.1785, "lon": 131.4737},
    "tokushima": {"name": "徳島県 (徳島)", "lat": 34.0711, "lon": 134.5516},
    "takamatsu": {"name": "香川県 (高松)", "lat": 34.3428, "lon": 134.0466},
    "matsuyama": {"name": "愛媛県 (松山)", "lat": 33.8392, "lon": 132.7654},
    "kochi": {"name": "高知県 (高知)", "lat": 33.5597, "lon": 133.5311},
    "fukuoka": {"name": "福岡県 (福岡)", "lat": 33.5904, "lon": 130.4017},
    "saga": {"name": "佐賀県 (佐賀)", "lat": 33.2635, "lon": 130.3009},
    "nagasaki": {"name": "長崎県 (長崎)", "lat": 32.7501, "lon": 129.8777},
    "kumamoto": {"name": "熊本県 (熊本)", "lat": 32.7898, "lon": 130.7417},
    "oita": {"name": "大分県 (大分)", "lat": 33.2382, "lon": 131.6126},
    "miyazaki": {"name": "宮崎県 (宮崎)", "lat": 31.9077, "lon": 131.4201},
    "kagoshima": {"name": "鹿児島県 (鹿児島)", "lat": 31.5966, "lon": 130.5571},
    "naha": {"name": "沖縄県 (那覇)", "lat": 26.2124, "lon": 127.6809},
}

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
    wbgt_by_date = database.get_wbgt_records_for_range(user_id, from_date, to_date)

    # 記録がある日付 + 範囲内の全日付を列挙（記録がない日も表示）
    dates = []
    cur = from_dt
    while cur <= to_dt:
        dates.append(cur.isoformat())
        cur += timedelta(days=1)
    # 記録が1件もない日は省く（すっきり表示のため）
    dates = [d for d in dates if d in records_by_date or d in notes_by_date or d in wbgt_by_date]

    user = database.get_user_by_username_by_id(user_id)
    username = user["username"] if user else ""
    location = user["location"] if user else "tokyo"
    location_name = CITIES.get(location, CITIES["tokyo"])["name"]
    
    current_medication = user["medication_timepoints"] if user and "medication_timepoints" in user.keys() else ""
    medication_tps = [tp.strip() for tp in current_medication.split(",") if tp.strip()] if current_medication else []

    # symptomsオブジェクトの辞書変換（Jinjaテンプレートで使いやすくするため）
    symptoms_list = [dict(s) for s in symptoms]

    return templates.TemplateResponse(
        "print.html",
        {
            "request": request,
            "username": username,
            "from_date": from_date,
            "to_date": to_date,
            "today": today_str,
            "symptoms": symptoms,
            "symptoms_json": json.dumps(symptoms_list),
            "dates": dates,
            "dates_json": json.dumps(dates),
            "records_by_date": records_by_date,
            "records_by_date_json": json.dumps(records_by_date),
            "notes_by_date": notes_by_date,
            "wbgt_records": wbgt_by_date,
            "wbgt_records_json": json.dumps(wbgt_by_date),
            "timepoints": TIMEPOINTS,
            "timepoint_labels": TIMEPOINT_LABELS,
            "location": location,
            "location_name": location_name,
            "medication_timepoints": medication_tps
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
    existing_wbgt = database.get_wbgt_record_for_date(user_id, today)
    note = database.get_note(user_id, today)
    symptoms = database.get_active_symptoms(user_id)
    
    user = database.get_user_by_username_by_id(user_id)
    location = user["location"] if user else "tokyo"
    location_name = CITIES.get(location, CITIES["tokyo"])["name"]
    
    current_medication = user["medication_timepoints"] if user and "medication_timepoints" in user.keys() else ""
    medication_tps = [tp.strip() for tp in current_medication.split(",") if tp.strip()] if current_medication else []

    return templates.TemplateResponse(
        "record.html",
        {
            "request": request,
            "date": today,
            "symptoms": symptoms,
            "timepoints": TIMEPOINTS,
            "timepoint_labels": TIMEPOINT_LABELS,
            "existing": json.dumps(existing),
            "existing_wbgt": json.dumps(existing_wbgt),
            "note": note,
            "location": location,
            "location_name": location_name,
            "medication_timepoints": medication_tps
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
    wbgt_data = body.get("wbgt_data")

    # date パラメータのバリデーション
    if date:
        try:
            date_type.fromisoformat(date)
        except ValueError:
            return JSONResponse({"error": "invalid date format"}, status_code=400)

    # note の長さを最大2000文字に制限（ストレージ枯渇対策）
    note = note[:2000]

    valid_symptoms = {s["name"] for s in database.get_all_symptoms(user_id)}

    # 1. 症状スコアのバリデーション (保存開始前に実行)
    for entry in entries:
        symptom = entry.get("symptom")
        timepoint = entry.get("timepoint")
        score = entry.get("score")

        is_medication = (symptom == "__medication__")
        
        # 服薬記録の場合は 'before_sleep' を含む時間帯を許容する
        allowed_tps = {"morning", "afternoon", "evening", "before_sleep", "overall"} if is_medication else set(TIMEPOINTS)
        
        if (not is_medication and symptom not in valid_symptoms) or timepoint not in allowed_tps:
            return JSONResponse({"error": "invalid data"}, status_code=400)
        if score is not None and score not in range(-1, 6):
            return JSONResponse({"error": "invalid score"}, status_code=400)

    # 2. WBGTデータのバリデーションと型変換 (保存開始前に実行)
    parsed_wbgt = None
    if wbgt_data:
        try:
            ta = float(wbgt_data.get("ta")) if wbgt_data.get("ta") is not None and wbgt_data.get("ta") != "" else None
            rh = float(wbgt_data.get("rh")) if wbgt_data.get("rh") is not None and wbgt_data.get("rh") != "" else None
            sr = float(wbgt_data.get("sr")) if wbgt_data.get("sr") is not None and wbgt_data.get("sr") != "" else None
            ws = float(wbgt_data.get("ws")) if wbgt_data.get("ws") is not None and wbgt_data.get("ws") != "" else None
            wbgt = float(wbgt_data.get("wbgt")) if wbgt_data.get("wbgt") is not None and wbgt_data.get("wbgt") != "" else None
            is_forecast = int(wbgt_data.get("is_forecast", 1))
            parsed_wbgt = {
                "ta": ta,
                "rh": rh,
                "sr": sr,
                "ws": ws,
                "wbgt": wbgt,
                "is_forecast": is_forecast
            }
        except ValueError:
            return JSONResponse({"error": "invalid wbgt values"}, status_code=400)

    # 3. アトミックな一括トランザクション保存の実行
    try:
        database.save_user_day_data(user_id, date, entries, note, parsed_wbgt)
    except Exception as e:
        print(f"[ERROR] Atomic save transaction failed: {e}")
        return JSONResponse({"error": "database save error"}, status_code=500)

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
        "wbgt": database.get_wbgt_record_for_date(user_id, date),
    })


def get_weather_from_api(lat: float, lon: float, date_str: str):
    import time
    # past_days=7 を付与して過去データも取得できるようにする
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation&wind_speed_unit=ms&timezone=Asia%2FTokyo&past_days=7"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'SymptoPort/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                hourly = data.get("hourly", {})
                times = hourly.get("time", [])
                
                # 各時間帯 (10:00, 11:00, 12:00, 13:00, 14:00) のインデックスを特定
                target_hours = ["10:00", "11:00", "12:00", "13:00", "14:00"]
                target_times = [f"{date_str}T{h}" for h in target_hours]
                
                indices = []
                for t in target_times:
                    if t in times:
                        indices.append(times.index(t))
                
                if not indices:
                    print(f"[WARNING] No target times found for date {date_str} on attempt {attempt+1}")
                    return None
                
                # 1. 気温 Ta ・ 湿度 RH は「10:00〜14:00の最大値 (MAX)」を使用
                tas = [hourly.get("temperature_2m", [])[i] for i in indices if hourly.get("temperature_2m", [])[i] is not None]
                ta = max(tas) if tas else 0.0
                
                rhs = [hourly.get("relative_humidity_2m", [])[i] for i in indices if hourly.get("relative_humidity_2m", [])[i] is not None]
                rh = max(rhs) if rhs else 0.0
                
                # 2. 全天日射量 SR は「10:00〜14:00の最大値 (MAX)」を使用
                sr_watts = [hourly.get("shortwave_radiation", [])[i] for i in indices if hourly.get("shortwave_radiation", [])[i] is not None]
                max_sr_watt = max(sr_watts) if sr_watts else 0.0
                sr = max_sr_watt / 1000.0  # W/m2 から kW/m2 への変換
                
                # 3. 平均風速 WS は「10:00〜14:00の最小値 (MIN)」を使用
                ws_speeds = [hourly.get("wind_speed_10m", [])[i] for i in indices if hourly.get("wind_speed_10m", [])[i] is not None]
                ws = min(ws_speeds) if ws_speeds else 0.0
                
                if ta is not None and rh is not None and sr is not None and ws is not None:
                    wbgt = (0.735 * ta 
                            + 0.0374 * rh 
                            + 0.00292 * ta * rh 
                            + 7.619 * sr 
                            - 4.557 * (sr ** 2) 
                            - 0.0572 * ws 
                            - 4.064)
                    wbgt_val = round(wbgt, 1) if wbgt >= 0 else None
                    return {"ta": ta, "rh": rh, "sr": round(sr, 3), "ws": ws, "wbgt": wbgt_val}
        except Exception as e:
            print(f"[WARNING] Fetching weather attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(1.0)  # 1秒ウェイトを入れて再試行
    return None


@app.get("/api/tokyo_weather")
async def get_tokyo_weather(
    date: str,
    force: int = 0,
    user_id: int = Depends(auth.get_current_user_id)
):
    from datetime import date as date_class
    
    # 日付形式のバリデーション
    try:
        date_class.fromisoformat(date)
    except ValueError:
        return JSONResponse({"error": "invalid date format"}, status_code=400)
        
    # ユーザー設定の居住地を取得
    user = database.get_user_by_username_by_id(user_id)
    location = user["location"] if user else "tokyo"
    city_info = CITIES.get(location, CITIES["tokyo"])
    lat = city_info["lat"]
    lon = city_info["lon"]
        
    # 現在の日本時間（JST = UTC+9）を取得
    tz_jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(tz_jst)
    today_jst_str = now_jst.date().isoformat()
    
    # 予報か実績かの判定
    if date < today_jst_str:
        is_forecast_status = 0
    elif date > today_jst_str:
        is_forecast_status = 1
    else: # 今日
        if now_jst.hour >= 14:
            is_forecast_status = 0
        else:
            is_forecast_status = 1
            
    # キャッシュキー：weather_14h_tokyo_2026-05-29
    cache_key = f"weather_14h_{location}_{date}"
    cache = database.get_weather_cache(cache_key)
    
    should_update = True
    if cache and not force:
        cache_is_forecast = cache.get("is_forecast", 1)
        
        # 1. キャッシュがすでに実測確定(0)の場合、再フェッチは不要
        if cache_is_forecast == 0:
            should_update = False
        # 2. キャッシュが予報値(1)で、現在ステータスも予報値(1)の場合、30分経っていなければ再フェッチしない
        elif cache_is_forecast == 1 and is_forecast_status == 1:
            try:
                updated_at = datetime.fromisoformat(cache["updated_at"])
                now_utc = datetime.now(timezone.utc)
                if now_utc - updated_at < timedelta(minutes=30):
                    should_update = False
            except ValueError:
                pass
            
    if should_update:
        new_data = get_weather_from_api(lat, lon, date)
        if new_data:
            now_utc = datetime.now(timezone.utc)
            database.set_weather_cache(
                cache_key,
                now_utc.isoformat(),
                new_data["ta"],
                new_data["rh"],
                new_data["sr"],
                new_data["ws"],
                new_data["wbgt"],
                is_forecast_status
            )
            new_data["is_forecast"] = is_forecast_status
            return JSONResponse(new_data)
            
    if cache:
        return JSONResponse({
            "ta": cache["ta"],
            "rh": cache["rh"],
            "sr": cache["sr"],
            "ws": cache["ws"],
            "wbgt": cache["wbgt"],
            "is_forecast": cache["is_forecast"],
            "cached": True
        })
        
    return JSONResponse({"error": "Weather data currently unavailable"}, status_code=503)


@app.post("/api/tokyo_weather/batch")
async def get_tokyo_weather_batch(
    request: Request,
    user_id: int = Depends(auth.get_current_user_id)
):
    from datetime import date as date_class, timedelta
    
    body = await request.json()
    from_date = body.get("from_date")
    to_date = body.get("to_date")
    force = body.get("force", 0)
    
    if not from_date or not to_date:
        return JSONResponse({"error": "missing parameters"}, status_code=400)
        
    try:
        fd = date_class.fromisoformat(from_date)
        td = date_class.fromisoformat(to_date)
    except ValueError:
        return JSONResponse({"error": "invalid date format"}, status_code=400)
        
    if fd > td:
        return JSONResponse({"error": "start date must be before end date"}, status_code=400)
        
    if (td - fd).days > 100:
        return JSONResponse({"error": "date range too wide (max 100 days)"}, status_code=400)
        
    # ユーザー設定の居住地を取得
    user = database.get_user_by_username_by_id(user_id)
    location = user["location"] if user else "tokyo"
    city_info = CITIES.get(location, CITIES["tokyo"])
    lat = city_info["lat"]
    lon = city_info["lon"]
        
    # アーカイブAPIで期間全体の実測気象データを一括取得（forecast APIより遡及範囲が広い）
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation&wind_speed_unit=ms&timezone=Asia%2FTokyo&start_date={from_date}&end_date={to_date}"
    
    import time
    max_retries = 3
    times = []
    hourly = {}
    success = False
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'SymptoPort/1.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                hourly = data.get("hourly", {})
                times = hourly.get("time", [])
                success = True
                break
        except Exception as e:
            print(f"[WARNING] Fetching weather batch attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(1.0)  # 1秒ウェイトを入れて再試行
                
    if not success:
        return JSONResponse({"error": "Failed to fetch weather data from external API after retries"}, status_code=502)
        
    # 現在の日本時間（JST）
    tz_jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(tz_jst)
    today_jst_str = now_jst.date().isoformat()
    
    # 1日ずつループして計算し、DBへ一括upsert
    cur = fd
    count = 0
    while cur <= td:
        date_str = cur.isoformat()
        cache_key = f"weather_14h_{location}_{date_str}"
        
        # 予報か実績かの判定
        if date_str < today_jst_str:
            is_forecast_status = 0
        elif date_str > today_jst_str:
            is_forecast_status = 1
        else: # 今日
            is_forecast_status = 0 if now_jst.hour >= 14 else 1
            
        # force=0の場合、すでに「実測確定」のキャッシュがあるならAPIからの再計算・保存をスキップできる
        if force == 0:
            existing_cache = database.get_weather_cache(cache_key)
            if existing_cache and existing_cache.get("is_forecast") == 0:
                cur += timedelta(days=1)
                continue
                
        target_hours = ["10:00", "11:00", "12:00", "13:00", "14:00"]
        target_times = [f"{date_str}T{h}" for h in target_hours]
        
        indices = []
        for t in target_times:
            if t in times:
                indices.append(times.index(t))
                
        if indices:
            try:
                # 10:00〜14:00 最大Ta, RH
                tas = [hourly.get("temperature_2m", [])[i] for i in indices if hourly.get("temperature_2m", [])[i] is not None]
                ta = max(tas) if tas else 0.0

                rhs = [hourly.get("relative_humidity_2m", [])[i] for i in indices if hourly.get("relative_humidity_2m", [])[i] is not None]
                rh = max(rhs) if rhs else 0.0

                # 10:00〜14:00 最大SR
                sr_watts = [hourly.get("shortwave_radiation", [])[i] for i in indices if hourly.get("shortwave_radiation", [])[i] is not None]
                max_sr_watt = max(sr_watts) if sr_watts else 0.0
                sr = max_sr_watt / 1000.0

                # 10:00〜14:00 最小WS
                ws_speeds = [hourly.get("wind_speed_10m", [])[i] for i in indices if hourly.get("wind_speed_10m", [])[i] is not None]
                ws = min(ws_speeds) if ws_speeds else 0.0

                if ta is not None and rh is not None and sr is not None and ws is not None:
                    wbgt = (0.735 * ta
                            + 0.0374 * rh
                            + 0.00292 * ta * rh
                            + 7.619 * sr
                            - 4.557 * (sr ** 2)
                            - 0.0572 * ws
                            - 4.064)
                    wbgt_val = round(wbgt, 1) if wbgt >= 0 else None

                    # DBキャッシュの更新
                    now_utc = datetime.now(timezone.utc)
                    database.set_weather_cache(
                        cache_key,
                        now_utc.isoformat(),
                        ta, rh, round(sr, 3), ws, wbgt_val,
                        is_forecast_status
                    )

                    # ユーザーの記録（wbgt_records）に一括保存
                    database.upsert_wbgt_record(
                        user_id, date_str,
                        ta, rh, round(sr, 3), ws, wbgt_val,
                        is_forecast_status
                    )
                    count += 1
            except Exception as e:
                print(f"[WARNING] Batch processing failed for {date_str}: {e}")

        cur += timedelta(days=1)
        
    return JSONResponse({"ok": True, "count": count})




# ---- 症状管理 ----

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    error: Optional[str] = None,
    user_id: int = Depends(auth.get_current_user_id),
):
    symptoms = database.get_all_symptoms(user_id)
    user = database.get_user_by_username_by_id(user_id)
    current_location = user["location"] if user else "tokyo"
    current_medication = user["medication_timepoints"] if user and "medication_timepoints" in user.keys() else ""
    medication_list = [tp.strip() for tp in current_medication.split(",") if tp.strip()] if current_medication else []
    
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "symptoms": symptoms,
            "cities": CITIES,
            "current_location": current_location,
            "medication_list": medication_list,
            "error": error
        },
    )


@app.post("/settings/location")
async def update_location(
    location: str = Form(...),
    user_id: int = Depends(auth.get_current_user_id),
):
    if location in CITIES:
        database.update_user_location(user_id, location)
    return RedirectResponse(url="/settings", status_code=302)


@app.post("/settings/medication")
async def update_medication(
    timepoints: list[str] = Form(default=[]),
    user_id: int = Depends(auth.get_current_user_id),
):
    valid_tps = {"morning", "afternoon", "evening", "before_sleep", "overall"}
    filtered_tps = [tp for tp in timepoints if tp in valid_tps]
    database.update_user_medication(user_id, ",".join(filtered_tps))
    return RedirectResponse(url="/settings", status_code=302)


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


@app.get("/api/backup")
async def export_backup(
    user_id: int = Depends(auth.get_current_user_id),
):
    backup_data = database.get_user_backup_data(user_id)
    json_str = json.dumps(backup_data, ensure_ascii=False, indent=2)
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"symptoport_backup_{today_str}.json"
    
    return Response(
        content=json_str,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@app.post("/api/restore")
async def import_restore(
    file: UploadFile = File(...),
    user_id: int = Depends(auth.get_current_user_id),
):
    MAX_SIZE = 5 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        return JSONResponse({"error": "ファイルサイズが大きすぎます (最大5MB)"}, status_code=400)
        
    try:
        backup_data = json.loads(content.decode("utf-8"))
    except Exception:
        return JSONResponse({"error": "不正なJSON形式です"}, status_code=400)
        
    required_keys = {"version", "symptoms", "records", "notes", "wbgt_records"}
    if not required_keys.issubset(backup_data.keys()):
        return JSONResponse({"error": "不正なバックアップスキーマです"}, status_code=400)
        
    try:
        database.restore_user_backup_data(user_id, backup_data)
        return JSONResponse({"ok": True})
    except Exception as e:
        print(f"[ERROR] Restore failed: {e}")
        return JSONResponse({"error": "データベースへの復元に失敗しました"}, status_code=500)


@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc):
    return RedirectResponse(url="/login", status_code=302)
