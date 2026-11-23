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
    _migrate(con)
    return con


def _migrate(con: sqlite3.Connection) -> None:
    """Upgrade databases created by older versions of the app."""
    cols = {r[1] for r in con.execute("PRAGMA table_info(calls)")}
    if "mobile" not in cols:
        con.execute("ALTER TABLE calls ADD COLUMN mobile TEXT")
        # Fill in executive / mobile / campaign from file names for calls saved before.
        from .filenames import parse_file_name
        for cid, fname, ex, camp in con.execute(
                "SELECT id, file_name, executive, campaign FROM calls").fetchall():
            g = parse_file_name(fname or "")
            con.execute("UPDATE calls SET mobile=?, executive=?, campaign=? WHERE id=?",
                        (g["mobile"] or None, (ex or "").strip() or g["executive"] or None,
                         (camp or "").strip() or g["campaign"] or None, cid))
        con.commit()


def add_call(meta: dict) -> int:
    with connect() as con:
        cur = con.execute(
            "INSERT INTO calls (uploaded_at, file_name, executive, mobile, call_date, campaign, pitch_version, status)"
            " VALUES (?,?,?,?,?,?,?, 'processing')",
            (datetime.now().isoformat(timespec="seconds"), meta["file_name"], meta.get("executive"),
             meta.get("mobile"), meta.get("call_date"), meta.get("campaign"), meta.get("pitch_version")))
        return cur.lastrowid


def save_review(call_id: int, review: dict, duration: float) -> None:
    with connect() as con:
        con.execute("UPDATE calls SET status='done', error=NULL, review_json=?, duration_sec=? WHERE id=?",
                    (json.dumps(review, ensure_ascii=False), duration, call_id))


def save_error(call_id: int, error: str) -> None:
    with connect() as con:
        con.execute("UPDATE calls SET status='error', error=? WHERE id=?", (error[:2000], call_id))


def update_meta(call_id: int, **fields) -> None:
    allowed = {"executive", "mobile", "call_date", "campaign", "pitch_version"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    with connect() as con:
        con.execute(f"UPDATE calls SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), call_id))


def delete_call(call_id: int) -> None:
    delete_calls([call_id])


def delete_calls(call_ids: list[int]) -> int:
    if not call_ids:
        return 0
    with connect() as con:
        cur = con.execute(f"DELETE FROM calls WHERE id IN ({','.join('?' * len(call_ids))})",
                          [int(i) for i in call_ids])
        return cur.rowcount


def delete_all(include_reports: bool = True) -> None:
    """Remove every stored review (and optionally every AI insights report)."""
    with connect() as con:
        con.execute("DELETE FROM calls")
        if include_reports:
            con.execute("DELETE FROM reports")
    with connect() as con:
        con.execute("VACUUM")


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
