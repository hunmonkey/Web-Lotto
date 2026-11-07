"""SQLite 한 파일(DATA_DIR/lotto.sqlite). 표 둘: rounds(과거 당첨번호) · favorites(즐겨찾기).
표를 바꿀 일이 생기면 SCHEMA 에 CREATE TABLE IF NOT EXISTS / ALTER 를 더한다(ORM · alembic 없음)."""
import sqlite3
from contextlib import closing

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS rounds (
    round    INTEGER PRIMARY KEY,
    drawn_on TEXT,
    n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
    n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL,
    bonus    INTEGER
);
CREATE TABLE IF NOT EXISTS favorites (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nums       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def _connect() -> sqlite3.Connection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(settings.data_dir / "lotto.sqlite")
    db.row_factory = sqlite3.Row
    return db


def init() -> None:
    with closing(_connect()) as db, db:
        db.executescript(SCHEMA)


# ---------- 과거 당첨번호 ----------
def upsert_rounds(rows: list[dict]) -> tuple[int, int]:
    """회차가 같으면 덮어쓴다. (새로 넣은 수, 덮어쓴 수)."""
    with closing(_connect()) as db, db:
        have = {r[0] for r in db.execute("SELECT round FROM rounds")}
        db.executemany(
            """INSERT INTO rounds (round, drawn_on, n1, n2, n3, n4, n5, n6, bonus)
               VALUES (:round, :drawn_on, :n1, :n2, :n3, :n4, :n5, :n6, :bonus)
               ON CONFLICT(round) DO UPDATE SET
                 drawn_on = COALESCE(excluded.drawn_on, rounds.drawn_on),
                 n1 = excluded.n1, n2 = excluded.n2, n3 = excluded.n3,
                 n4 = excluded.n4, n5 = excluded.n5, n6 = excluded.n6,
                 bonus = COALESCE(excluded.bonus, rounds.bonus)""",
            [
                {"round": r["round"], "drawn_on": r["drawn_on"], "bonus": r["bonus"],
                 **{f"n{k + 1}": n for k, n in enumerate(r["nums"])}}
                for r in rows
            ],
        )
    added = sum(1 for r in rows if r["round"] not in have)
    return added, len(rows) - added


def list_rounds(limit: int) -> list[dict]:
    with closing(_connect()) as db:
        cur = db.execute("SELECT * FROM rounds ORDER BY round DESC LIMIT ?", (limit,))
        return [
            {"round": r["round"], "drawn_on": r["drawn_on"], "bonus": r["bonus"],
             "nums": [r[f"n{k}"] for k in range(1, 7)]}
            for r in cur
        ]


def round_stats() -> dict:
    with closing(_connect()) as db:
        total, first, last = db.execute("SELECT COUNT(*), MIN(round), MAX(round) FROM rounds").fetchone()
    return {"total": total, "first": first, "last": last}


def frequency() -> list[int]:
    """번호별로 (보너스를 뺀) 당첨번호에 나온 횟수. 0 번 칸은 비워 두고 1~45 를 쓴다."""
    freq = [0] * 46
    with closing(_connect()) as db:
        for row in db.execute("SELECT n1, n2, n3, n4, n5, n6 FROM rounds"):
            for n in row:
                freq[n] += 1
    return freq


# ---------- 즐겨찾기 ----------
def list_favs() -> list[dict]:
    with closing(_connect()) as db:
        return [
            {"id": r["id"], "nums": [int(x) for x in r["nums"].split(",")]}
            for r in db.execute("SELECT id, nums FROM favorites ORDER BY id DESC")
        ]


def add_fav(nums: list[int]) -> None:
    """같은 번호는 한 번만 둔다."""
    with closing(_connect()) as db, db:
        db.execute("INSERT OR IGNORE INTO favorites (nums) VALUES (?)", (",".join(map(str, sorted(nums))),))


def del_fav(fav_id: int) -> None:
    with closing(_connect()) as db, db:
        db.execute("DELETE FROM favorites WHERE id = ?", (fav_id,))
