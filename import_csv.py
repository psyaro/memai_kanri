"""
CSVインポートスクリプト
Usage: python import_csv.py <csvファイルパス> <ユーザー名>
"""
import sys
import csv
import database

# CSVの列 → (symptom, timepoint)
COLUMN_MAP = {
    "昨晩睡眠":  ("sleep",     "overall"),
    "ほてり朝":  ("flushing",  "morning"),
    "ほてり昼":  ("flushing",  "afternoon"),
    "ほてり夜":  ("flushing",  "evening"),
    "ほてり全":  ("flushing",  "overall"),
    "めまい朝":  ("dizziness", "morning"),
    "めまい昼":  ("dizziness", "afternoon"),
    "めまい夜":  ("dizziness", "evening"),
    "めまい全":  ("dizziness", "overall"),
    "倦怠感朝":  ("fatigue",   "morning"),
    "倦怠感昼":  ("fatigue",   "afternoon"),
    "倦怠感夜":  ("fatigue",   "evening"),
    "倦怠感全":  ("fatigue",   "overall"),
    "メンタル朝": ("mental",   "morning"),
    "メンタル昼": ("mental",   "afternoon"),
    "メンタル夜": ("mental",   "evening"),
    "メンタル全": ("mental",   "overall"),
}


def parse_score(val: str):
    v = val.strip()
    if v == "" or v == "-":
        return None       # 未入力
    if v == "なし":
        return -1         # なし
    try:
        n = int(v)
        if 0 <= n <= 5:
            return n
    except ValueError:
        pass
    return None


def main():
    if len(sys.argv) != 3:
        print("Usage: python import_csv.py <csvファイル> <ユーザー名>")
        sys.exit(1)

    csv_path, username = sys.argv[1], sys.argv[2]

    database.init_db()
    user = database.get_user_by_username(username)
    if not user:
        print(f"Error: ユーザー '{username}' が見つかりません")
        sys.exit(1)
    user_id = user["id"]

    imported = 0
    skipped = 0

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_date = row.get("") or row.get("date", "")
            if not raw_date.strip():
                continue

            # YYYY/MM/DD → YYYY-MM-DD
            date = raw_date.strip().replace("/", "-")

            for col_name, (symptom, timepoint) in COLUMN_MAP.items():
                if col_name not in row:
                    continue
                score = parse_score(row[col_name])
                database.upsert_record(user_id, date, symptom, timepoint, score)

            note = row.get("備考", "").strip()
            if note:
                database.upsert_note(user_id, date, note)

            imported += 1

    print(f"完了: {imported}日分をインポートしました")


if __name__ == "__main__":
    main()
