import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "health.db")

_DEFAULT_SYMPTOMS = [
    ("sleep",     "昨晩の睡眠", 0, 0, 1), # name, label, use_timepoints, sort_order, is_reverse
    ("dizziness", "めまい",     1, 1, 0),
    ("flushing",  "ほてり",     1, 2, 0),
    ("fatigue",   "疲労感",     1, 3, 0),
    ("mental",    "メンタル",   1, 4, 1),
]


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                location TEXT DEFAULT 'tokyo',
                medication_timepoints TEXT DEFAULT ''
            );
        """)

        # symptomsテーブルのマイグレーション処理
        table_info = conn.execute("PRAGMA table_info(symptoms)").fetchall()
        if table_info:
            has_user_id = any(row["name"] == "user_id" for row in table_info)
            if not has_user_id:
                # 古いテーブルの名前を変更してバックアップ
                conn.execute("ALTER TABLE symptoms RENAME TO symptoms_old")
                
                # 新しいuser_id付きのテーブルを作成
                conn.execute("""
                    CREATE TABLE symptoms (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        name TEXT NOT NULL,
                        label TEXT NOT NULL,
                        use_timepoints INTEGER NOT NULL DEFAULT 1,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        active INTEGER NOT NULL DEFAULT 1,
                        is_reverse INTEGER NOT NULL DEFAULT 0,
                        UNIQUE(user_id, name)
                    );
                """)
                
                # 既存ユーザーの取得
                users = conn.execute("SELECT id FROM users").fetchall()
                # 旧データの取得
                old_symptoms = conn.execute("SELECT name, label, use_timepoints, sort_order, active FROM symptoms_old").fetchall()
                
                # 既存の全ユーザーに旧症状設定をコピー
                for user in users:
                    uid = user["id"]
                    for row in old_symptoms:
                        conn.execute(
                            """
                            INSERT INTO symptoms (user_id, name, label, use_timepoints, sort_order, active, is_reverse)
                            VALUES (?,?,?,?,?,?,0)
                            """,
                            (uid, row["name"], row["label"], row["use_timepoints"], row["sort_order"], row["active"])
                        )
                
                # 旧テーブルの削除
                conn.execute("DROP TABLE symptoms_old")
            
            # is_reverse カラムが無い場合は追加する
            table_info = conn.execute("PRAGMA table_info(symptoms)").fetchall()
            has_is_reverse = any(row["name"] == "is_reverse" for row in table_info)
            if not has_is_reverse:
                conn.execute("ALTER TABLE symptoms ADD COLUMN is_reverse INTEGER NOT NULL DEFAULT 0")
        else:
            # テーブルが存在しない場合は新規作成
            conn.execute("""
                CREATE TABLE symptoms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    name TEXT NOT NULL,
                    label TEXT NOT NULL,
                    use_timepoints INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    is_reverse INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(user_id, name)
                );
            """)

        # weather_cache.wbgt が NOT NULL の古いスキーマを修正（キャッシュのため消去OK）
        _cache_info = conn.execute("PRAGMA table_info(weather_cache)").fetchall()
        if _cache_info:
            _wbgt_col = next((r for r in _cache_info if r["name"] == "wbgt"), None)
            if _wbgt_col and _wbgt_col["notnull"] == 1:
                conn.execute("DROP TABLE weather_cache")

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                date TEXT NOT NULL,
                symptom TEXT NOT NULL,
                timepoint TEXT NOT NULL,
                score INTEGER,
                UNIQUE(user_id, date, symptom, timepoint)
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                date TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                UNIQUE(user_id, date)
            );
            CREATE TABLE IF NOT EXISTS wbgt_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                date TEXT NOT NULL,
                ta REAL,
                rh REAL,
                sr REAL,
                ws REAL,
                wbgt REAL,
                is_forecast INTEGER DEFAULT 1,
                UNIQUE(user_id, date)
            );
            CREATE TABLE IF NOT EXISTS weather_cache (
                key TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,
                ta REAL NOT NULL,
                rh REAL NOT NULL,
                sr REAL NOT NULL,
                ws REAL NOT NULL,
                wbgt REAL,
                is_forecast INTEGER DEFAULT 1
            );
        """)

        # wbgt_records テーブルのマイグレーション処理
        table_info_wbgt = conn.execute("PRAGMA table_info(wbgt_records)").fetchall()
        if table_info_wbgt:
            has_is_forecast = any(row["name"] == "is_forecast" for row in table_info_wbgt)
            if not has_is_forecast:
                conn.execute("ALTER TABLE wbgt_records ADD COLUMN is_forecast INTEGER DEFAULT 1")

        # weather_cache テーブルのマイグレーション処理
        table_info_cache = conn.execute("PRAGMA table_info(weather_cache)").fetchall()
        if table_info_cache:
            has_is_forecast = any(row["name"] == "is_forecast" for row in table_info_cache)
            if not has_is_forecast:
                conn.execute("ALTER TABLE weather_cache ADD COLUMN is_forecast INTEGER DEFAULT 1")

        # users テーブルのマイグレーション処理
        table_info_users = conn.execute("PRAGMA table_info(users)").fetchall()
        if table_info_users:
            has_location = any(row["name"] == "location" for row in table_info_users)
            if not has_location:
                conn.execute("ALTER TABLE users ADD COLUMN location TEXT DEFAULT 'tokyo'")
            
            has_medication = any(row["name"] == "medication_timepoints" for row in table_info_users)
            if not has_medication:
                conn.execute("ALTER TABLE users ADD COLUMN medication_timepoints TEXT DEFAULT ''")



@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---- users ----

def get_user_by_username(username: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()


def get_user_by_username_by_id(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def update_user_location(user_id: int, location: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET location = ? WHERE id = ?",
            (location, user_id),
        )


def update_user_medication(user_id: int, medication_timepoints: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET medication_timepoints = ? WHERE id = ?",
            (medication_timepoints, user_id),
        )


def create_user(username: str, password_hash: str, selected_symptoms: list[str] = None):
    # 初期状態で睡眠、メンタル、疲労感だけを有効にする
    if selected_symptoms is None:
        selected_symptoms = ["sleep", "mental", "fatigue"]

    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        user_id = cursor.lastrowid
        # 新規作成されたユーザーにデフォルト症状を追加
        for name, label, use_tp, order, is_rev in _DEFAULT_SYMPTOMS:
            active = 1 if name in selected_symptoms else 0
            conn.execute(
                "INSERT OR IGNORE INTO symptoms (user_id, name, label, use_timepoints, sort_order, active, is_reverse) VALUES (?,?,?,?,?,?,?)",
                (user_id, name, label, use_tp, order, active, is_rev),
            )


# ---- symptoms ----

def get_active_symptoms(user_id: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM symptoms WHERE user_id=? AND active=1 ORDER BY sort_order, id",
            (user_id,)
        ).fetchall()


def get_all_symptoms(user_id: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM symptoms WHERE user_id=? ORDER BY sort_order, id",
            (user_id,)
        ).fetchall()


def add_symptom(user_id: int, name: str, label: str, use_timepoints: int = 1, is_reverse: int = 0) -> bool:
    try:
        with get_conn() as conn:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order),0) FROM symptoms WHERE user_id=?",
                (user_id,)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO symptoms (user_id, name, label, use_timepoints, sort_order, is_reverse) VALUES (?,?,?,?,?,?)",
                (user_id, name, label, use_timepoints, max_order + 1, is_reverse),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_symptom(user_id: int, symptom_id: int, label: str, use_timepoints: int, active: int, is_reverse: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE symptoms SET label=?, use_timepoints=?, active=?, is_reverse=? WHERE id=? AND user_id=?",
            (label, use_timepoints, active, is_reverse, symptom_id, user_id),
        )


def reorder_symptoms(user_id: int, ordered_ids: list[int]):
    with get_conn() as conn:
        for i, sid in enumerate(ordered_ids):
            conn.execute(
                "UPDATE symptoms SET sort_order=? WHERE id=? AND user_id=?",
                (i, sid, user_id)
            )


# ---- records ----

def upsert_record(user_id: int, date: str, symptom: str, timepoint: str, score):
    with get_conn() as conn:
        if score is None:
            conn.execute(
                "DELETE FROM records WHERE user_id=? AND date=? AND symptom=? AND timepoint=?",
                (user_id, date, symptom, timepoint),
            )
        else:
            # なし=-1, 0〜5 をそのまま保存
            conn.execute(
                """
                INSERT INTO records (user_id, date, symptom, timepoint, score)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, date, symptom, timepoint)
                DO UPDATE SET score = excluded.score
                """,
                (user_id, date, symptom, timepoint, score),
            )


def get_records_for_date(user_id: int, date: str) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT symptom, timepoint, score FROM records WHERE user_id = ? AND date = ?",
            (user_id, date),
        ).fetchall()
    return {f"{r['symptom']}_{r['timepoint']}": r["score"] for r in rows}


# ---- notes ----

def upsert_note(user_id: int, date: str, body: str):
    with get_conn() as conn:
        if body.strip():
            conn.execute(
                """
                INSERT INTO notes (user_id, date, body) VALUES (?,?,?)
                ON CONFLICT(user_id, date) DO UPDATE SET body=excluded.body
                """,
                (user_id, date, body),
            )
        else:
            conn.execute(
                "DELETE FROM notes WHERE user_id=? AND date=?",
                (user_id, date),
            )


def get_note(user_id: int, date: str) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT body FROM notes WHERE user_id=? AND date=?",
            (user_id, date),
        ).fetchone()
    return row["body"] if row else ""


# ---- range queries (印刷用) ----

def get_records_for_range(user_id: int, start_date: str, end_date: str) -> dict:
    """指定日付範囲のレコードを {date: {symptom_timepoint: score}} で返す"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT date, symptom, timepoint, score FROM records
               WHERE user_id=? AND date>=? AND date<=?
               ORDER BY date""",
            (user_id, start_date, end_date),
        ).fetchall()
    result: dict = {}
    for r in rows:
        d = r["date"]
        if d not in result:
            result[d] = {}
        result[d][f"{r['symptom']}_{r['timepoint']}"] = r["score"]
    return result


def get_notes_for_range(user_id: int, start_date: str, end_date: str) -> dict:
    """指定日付範囲のノートを {date: body} で返す"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT date, body FROM notes
               WHERE user_id=? AND date>=? AND date<=?""",
            (user_id, start_date, end_date),
        ).fetchall()
    return {r["date"]: r["body"] for r in rows}


# ---- WBGT & Weather Cache (ベータ版) ----

def upsert_wbgt_record(user_id: int, date: str, ta, rh, sr, ws, wbgt, is_forecast):
    with get_conn() as conn:
        # すべて値が空（None）であれば削除する
        if ta is None and rh is None and sr is None and ws is None and wbgt is None:
            conn.execute(
                "DELETE FROM wbgt_records WHERE user_id=? AND date=?",
                (user_id, date),
            )
        else:
            conn.execute(
                """
                INSERT INTO wbgt_records (user_id, date, ta, rh, sr, ws, wbgt, is_forecast)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, date)
                DO UPDATE SET ta=excluded.ta, rh=excluded.rh, sr=excluded.sr, ws=excluded.ws, wbgt=excluded.wbgt, is_forecast=excluded.is_forecast
                """,
                (user_id, date, ta, rh, sr, ws, wbgt, is_forecast),
            )


def get_wbgt_record_for_date(user_id: int, date: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ta, rh, sr, ws, wbgt, is_forecast FROM wbgt_records WHERE user_id=? AND date=?",
            (user_id, date),
        ).fetchone()
    return dict(row) if row else {}


def get_wbgt_records_for_range(user_id: int, start_date: str, end_date: str) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT date, ta, rh, sr, ws, wbgt, is_forecast FROM wbgt_records
               WHERE user_id=? AND date>=? AND date<=?
               ORDER BY date""",
            (user_id, start_date, end_date),
        ).fetchall()
    return {r["date"]: dict(r) for r in rows}


def get_weather_cache(key: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT updated_at, ta, rh, sr, ws, wbgt, is_forecast FROM weather_cache WHERE key=?",
            (key,),
        ).fetchone()
    return dict(row) if row else {}


def set_weather_cache(key: str, updated_at: str, ta: float, rh: float, sr: float, ws: float, wbgt: float, is_forecast: int):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weather_cache (key, updated_at, ta, rh, sr, ws, wbgt, is_forecast)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key)
            DO UPDATE SET updated_at=excluded.updated_at, ta=excluded.ta, rh=excluded.rh, sr=excluded.sr, ws=excluded.ws, wbgt=excluded.wbgt, is_forecast=excluded.is_forecast
            """,
            (key, updated_at, ta, rh, sr, ws, wbgt, is_forecast),
        )


def get_user_backup_data(user_id: int) -> dict:
    with get_conn() as conn:
        user_row = conn.execute("SELECT username, location, medication_timepoints FROM users WHERE id = ?", (user_id,)).fetchone()
        user_info = dict(user_row) if user_row else {}
        
        symptoms_rows = conn.execute("SELECT name, label, use_timepoints, sort_order, active, is_reverse FROM symptoms WHERE user_id = ?", (user_id,)).fetchall()
        symptoms = [dict(r) for r in symptoms_rows]
        
        records_rows = conn.execute("SELECT date, symptom, timepoint, score FROM records WHERE user_id = ?", (user_id,)).fetchall()
        records = [dict(r) for r in records_rows]
        
        notes_rows = conn.execute("SELECT date, body FROM notes WHERE user_id = ?", (user_id,)).fetchall()
        notes = [dict(r) for r in notes_rows]
        
        wbgt_rows = conn.execute("SELECT date, ta, rh, sr, ws, wbgt, is_forecast FROM wbgt_records WHERE user_id = ?", (user_id,)).fetchall()
        wbgt_records = [dict(r) for r in wbgt_rows]
        
    return {
        "version": "1.0",
        "username": user_info.get("username", ""),
        "location": user_info.get("location", "tokyo"),
        "medication_timepoints": user_info.get("medication_timepoints", ""),
        "symptoms": symptoms,
        "records": records,
        "notes": notes,
        "wbgt_records": wbgt_records
    }


def restore_user_backup_data(user_id: int, backup_data: dict):
    with get_conn() as conn:
        # 1. 既存データの全削除
        conn.execute("DELETE FROM records WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM notes WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM wbgt_records WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM symptoms WHERE user_id = ?", (user_id,))
        
        # 2. ユーザー設定の復元
        location = backup_data.get("location", "tokyo")
        medication_timepoints = backup_data.get("medication_timepoints", "")
        conn.execute("UPDATE users SET location = ?, medication_timepoints = ? WHERE id = ?", (location, medication_timepoints, user_id))
        
        # 3. 症状定義のインサート
        for s in backup_data.get("symptoms", []):
            conn.execute(
                """
                INSERT INTO symptoms (user_id, name, label, use_timepoints, sort_order, active, is_reverse)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, s["name"], s["label"], s["use_timepoints"], s["sort_order"], s["active"], s["is_reverse"])
            )
            
        # 4. 記録のインサート
        for r in backup_data.get("records", []):
            conn.execute(
                """
                INSERT INTO records (user_id, date, symptom, timepoint, score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, r["date"], r["symptom"], r["timepoint"], r["score"])
            )
            
        # 5. 備考メモのインサート
        for n in backup_data.get("notes", []):
            conn.execute(
                """
                INSERT INTO notes (user_id, date, body)
                VALUES (?, ?, ?)
                """,
                (user_id, n["date"], n["body"])
            )
            
        # 6. WBGT記録のインサート
        for w in backup_data.get("wbgt_records", []):
            conn.execute(
                """
                INSERT INTO wbgt_records (user_id, date, ta, rh, sr, ws, wbgt, is_forecast)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, w["date"], w.get("ta"), w.get("rh"), w.get("sr"), w.get("ws"), w.get("wbgt"), w.get("is_forecast", 1))
            )


def save_user_day_data(user_id: int, date: str, entries: list, note: str, wbgt_data: dict = None):
    with get_conn() as conn:
        # 1. 症状スコアの保存
        for entry in entries:
            symptom = entry.get("symptom")
            timepoint = entry.get("timepoint")
            score = entry.get("score")
            
            if score is None:
                conn.execute(
                    "DELETE FROM records WHERE user_id=? AND date=? AND symptom=? AND timepoint=?",
                    (user_id, date, symptom, timepoint),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO records (user_id, date, symptom, timepoint, score)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, date, symptom, timepoint)
                    DO UPDATE SET score = excluded.score
                    """,
                    (user_id, date, symptom, timepoint, score),
                )
        
        # 2. 備考の保存
        if note.strip():
            conn.execute(
                """
                INSERT INTO notes (user_id, date, body) VALUES (?,?,?)
                ON CONFLICT(user_id, date) DO UPDATE SET body=excluded.body
                """,
                (user_id, date, note),
            )
        else:
            conn.execute(
                "DELETE FROM notes WHERE user_id=? AND date=?",
                (user_id, date),
            )
            
        # 3. WBGTデータの保存
        if wbgt_data:
            ta = wbgt_data.get("ta")
            rh = wbgt_data.get("rh")
            sr = wbgt_data.get("sr")
            ws = wbgt_data.get("ws")
            wbgt = wbgt_data.get("wbgt")
            is_forecast = wbgt_data.get("is_forecast", 1)
            
            conn.execute(
                """
                INSERT INTO wbgt_records (user_id, date, ta, rh, sr, ws, wbgt, is_forecast)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, date)
                DO UPDATE SET ta=excluded.ta, rh=excluded.rh, sr=excluded.sr, ws=excluded.ws, wbgt=excluded.wbgt, is_forecast=excluded.is_forecast
                """,
                (user_id, date, ta, rh, sr, ws, wbgt, is_forecast),
            )
        else:
            conn.execute(
                "DELETE FROM wbgt_records WHERE user_id=? AND date=?",
                (user_id, date),
            )


