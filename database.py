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
                password_hash TEXT NOT NULL
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
        """)


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
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        user_id = cursor.lastrowid
        # 新規作成されたユーザーにデフォルト症状を追加
        for name, label, use_tp, order, is_rev in _DEFAULT_SYMPTOMS:
            conn.execute(
                "INSERT OR IGNORE INTO symptoms (user_id, name, label, use_timepoints, sort_order, is_reverse) VALUES (?,?,?,?,?,?)",
                (user_id, name, label, use_tp, order, is_rev),
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
