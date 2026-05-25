import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "health.db")

_DEFAULT_SYMPTOMS = [
    ("sleep",     "昨晩の睡眠", 0, 0),
    ("dizziness", "めまい",     1, 1),
    ("flushing",  "ほてり",     1, 2),
    ("fatigue",   "疲労感",     1, 3),
    ("mental",    "メンタル",   1, 4),
]


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS symptoms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL,
                use_timepoints INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            );
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
        """)
        for name, label, use_tp, order in _DEFAULT_SYMPTOMS:
            conn.execute(
                "INSERT OR IGNORE INTO symptoms (name, label, use_timepoints, sort_order) VALUES (?,?,?,?)",
                (name, label, use_tp, order),
            )


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


def create_user(username: str, password_hash: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )


# ---- symptoms ----

def get_active_symptoms() -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM symptoms WHERE active=1 ORDER BY sort_order, id"
        ).fetchall()


def get_all_symptoms() -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM symptoms ORDER BY sort_order, id"
        ).fetchall()


def add_symptom(name: str, label: str, use_timepoints: int = 1) -> bool:
    try:
        with get_conn() as conn:
            max_order = conn.execute("SELECT COALESCE(MAX(sort_order),0) FROM symptoms").fetchone()[0]
            conn.execute(
                "INSERT INTO symptoms (name, label, use_timepoints, sort_order) VALUES (?,?,?,?)",
                (name, label, use_timepoints, max_order + 1),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_symptom(symptom_id: int, label: str, use_timepoints: int, active: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE symptoms SET label=?, use_timepoints=?, active=? WHERE id=?",
            (label, use_timepoints, active, symptom_id),
        )


def reorder_symptoms(ordered_ids: list[int]):
    with get_conn() as conn:
        for i, sid in enumerate(ordered_ids):
            conn.execute("UPDATE symptoms SET sort_order=? WHERE id=?", (i, sid))


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
