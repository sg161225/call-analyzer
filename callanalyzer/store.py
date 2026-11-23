"""SQLite storage for call reviews (no audio, no transcripts)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pandas as pd

from .config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    uploaded_at   TEXT NOT NULL,
    file_name     TEXT NOT NULL,
    executive     TEXT,
    call_date     TEXT,
    campaign      TEXT,
    pitch_version TEXT,
    duration_sec  REAL,
    status        TEXT NOT NULL,      -- processing | done | error
    error         TEXT,
    review_json   TEXT
);
CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    scope       TEXT,
    content_md  TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def add_call(meta: dict) -> int:
    with connect() as con:
        cur = con.execute(
            "INSERT INTO calls (uploaded_at, file_name, executive, call_date, campaign, pitch_version, status)"
            " VALUES (?,?,?,?,?,?, 'processing')",
            (datetime.now().isoformat(timespec="seconds"), meta["file_name"], meta.get("executive"),
             meta.get("call_date"), meta.get("campaign"), meta.get("pitch_version")))
        return cur.lastrowid


def save_review(call_id: int, review: dict, duration: float) -> None:
    with connect() as con:
        con.execute("UPDATE calls SET status='done', error=NULL, review_json=?, duration_sec=? WHERE id=?",
                    (json.dumps(review, ensure_ascii=False), duration, call_id))


def save_error(call_id: int, error: str) -> None:
    with connect() as con:
        con.execute("UPDATE calls SET status='error', error=? WHERE id=?", (error[:2000], call_id))


def update_meta(call_id: int, **fields) -> None:
    allowed = {"executive", "call_date", "campaign", "pitch_version"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    with connect() as con:
        con.execute(f"UPDATE calls SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), call_id))


def delete_call(call_id: int) -> None:
    with connect() as con:
        con.execute("DELETE FROM calls WHERE id=?", (call_id,))


def load_calls() -> pd.DataFrame:
    with connect() as con:
        df = pd.read_sql_query("SELECT * FROM calls ORDER BY call_date DESC, id DESC", con)
    df["review"] = df["review_json"].apply(lambda s: json.loads(s) if isinstance(s, str) and s else None)
    return df


def save_report(scope: str, content_md: str) -> None:
    with connect() as con:
        con.execute("INSERT INTO reports (created_at, scope, content_md) VALUES (?,?,?)",
                    (datetime.now().isoformat(timespec="seconds"), scope, content_md))


def load_reports() -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM reports ORDER BY id DESC")]
