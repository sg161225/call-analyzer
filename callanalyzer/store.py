"""Storage for call reviews (no audio, no transcripts).

Uses a local SQLite file by default (data/calls.db). When the DATABASE_URL setting is present,
e.g. a free Neon / Supabase Postgres database for the online version, it uses that instead, so
reviews survive restarts and are shared by everyone using the hosted app.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from functools import lru_cache

import pandas as pd
from sqlalchemy import (Column, Float, Integer, LargeBinary, MetaData, Table, Text, create_engine, delete,
                        inspect, insert, select, text, update)
from sqlalchemy.engine import Engine

from .config import DATA_DIR, DB_PATH

metadata = MetaData()
calls = Table(
    "calls", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("uploaded_at", Text, nullable=False),
    Column("file_name", Text, nullable=False),
    Column("executive", Text),
    Column("mobile", Text),
    Column("call_type", Text),
    Column("call_date", Text),
    Column("campaign", Text),
    Column("pitch_version", Text),
    Column("duration_sec", Float),
    Column("status", Text, nullable=False),  # processing | done | error
    Column("error", Text),
    Column("review_json", Text),
    Column("followup_done", Integer),
    Column("transcript_json", Text),   # timed segments [{start, end, text}]
    Column("audio_stats", Text),       # {"dead_air": {...}} measured from the audio
)
recordings = Table(
    "recordings", metadata,
    Column("call_id", Integer, primary_key=True),
    Column("mime", Text, nullable=False),
    Column("audio", LargeBinary, nullable=False),
    Column("peaks_json", Text),
    Column("created_at", Text),
)
reports = Table(
    "reports", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", Text, nullable=False),
    Column("scope", Text),
    Column("content_md", Text, nullable=False),
    Column("content_json", Text),   # structured report for the visual dashboard
    Column("call_ids", Text),       # JSON list of the calls the report covers
)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Neon / Supabase / Heroku style URLs -> SQLAlchemy psycopg2 driver.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg2://" + url[len(prefix):]
        return url
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DB_PATH}"


def is_online_db() -> bool:
    return not database_url().startswith("sqlite")


def storage_label() -> str:
    if is_online_db():
        host = database_url().split("@")[-1].split("/")[0].split("?")[0]
        return f"online database ({host})"
    return f"local file {DB_PATH}"


@lru_cache(maxsize=4)
def _engine_for(url: str) -> Engine:
    eng = create_engine(url, pool_pre_ping=True, future=True)
    metadata.create_all(eng)
    _migrate(eng)
    _rename_legacy_types(eng)
    return eng


def engine() -> Engine:
    return _engine_for(database_url())


def _migrate(eng: Engine) -> None:
    """Upgrade databases created by older versions of the app."""
    rcols = {c["name"] for c in inspect(eng).get_columns("reports")}
    for col in ("content_json", "call_ids"):
        if col not in rcols:
            with eng.begin() as con:
                con.execute(text(f"ALTER TABLE reports ADD COLUMN {col} TEXT"))
    cols = {c["name"] for c in inspect(eng).get_columns("calls")}
    if "mobile" not in cols:
        from .filenames import parse_file_name
        with eng.begin() as con:
            con.execute(text("ALTER TABLE calls ADD COLUMN mobile TEXT"))
            # Fill in executive / mobile / campaign from file names for calls saved before.
            rows = con.execute(text("SELECT id, file_name, executive, campaign FROM calls")).all()
            for cid, fname, ex, camp in rows:
                g = parse_file_name(fname or "")
                con.execute(update(calls).where(calls.c.id == cid).values(
                    mobile=g["mobile"] or None,
                    executive=(ex or "").strip() or g["executive"] or None,
                    campaign=(camp or "").strip() or g["campaign"] or None))
    for col in ("transcript_json", "audio_stats"):
        if col not in cols:
            with eng.begin() as con:
                con.execute(text(f"ALTER TABLE calls ADD COLUMN {col} TEXT"))
    if "followup_done" not in cols:
        with eng.begin() as con:
            con.execute(text("ALTER TABLE calls ADD COLUMN followup_done INTEGER"))
    if "call_type" not in cols:
        from .calltypes import guess_type_from_purpose
        with eng.begin() as con:
            con.execute(text("ALTER TABLE calls ADD COLUMN call_type TEXT"))
            # Older reviews have no call type: classify from the AI's 'call purpose'.
            for cid, rj in con.execute(text("SELECT id, review_json FROM calls")).all():
                if rj:
                    rv = json.loads(rj)
                    ct = rv.get("call_type") or guess_type_from_purpose(rv.get("call_purpose", ""))
                    con.execute(update(calls).where(calls.c.id == cid).values(call_type=ct))


def _rename_legacy_types(eng: Engine) -> None:
    """CLM was split into 'CLM Onboarding' and 'CLM Existing'; earlier CLM calls were existing-customer calls."""
    with eng.begin() as con:
        con.execute(update(calls).where(calls.c.call_type == "CLM").values(call_type="CLM Existing"))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def add_call(meta: dict) -> int:
    with engine().begin() as con:
        res = con.execute(insert(calls).values(
            uploaded_at=_now(), file_name=meta["file_name"], executive=meta.get("executive"),
            mobile=meta.get("mobile"), call_type=meta.get("call_type") or None,
            call_date=meta.get("call_date"), campaign=meta.get("campaign"),
            pitch_version=meta.get("pitch_version"), status="processing"))
        return int(res.inserted_primary_key[0])


def save_review(call_id: int, review: dict, duration: float) -> None:
    with engine().begin() as con:
        con.execute(update(calls).where(calls.c.id == call_id).values(
            status="done", error=None, review_json=json.dumps(review, ensure_ascii=False),
            duration_sec=float(duration), call_type=review.get("call_type")))


def save_transcript(call_id: int, segments: list, audio_stats: dict, duration: float | None = None) -> None:
    values = {"transcript_json": json.dumps(segments, ensure_ascii=False), "audio_stats": json.dumps(audio_stats)}
    if duration:
        values["duration_sec"] = float(duration)
    with engine().begin() as con:
        con.execute(update(calls).where(calls.c.id == call_id).values(**values))


def save_recording(call_id: int, audio: bytes, mime: str, peaks: list) -> None:
    with engine().begin() as con:
        con.execute(delete(recordings).where(recordings.c.call_id == call_id))
        con.execute(insert(recordings).values(call_id=call_id, mime=mime, audio=audio,
                                              peaks_json=json.dumps(peaks), created_at=_now()))


def get_recording(call_id: int) -> dict | None:
    with engine().connect() as con:
        r = con.execute(select(recordings).where(recordings.c.call_id == int(call_id))).first()
    if not r:
        return None
    m = dict(r._mapping)
    m["peaks"] = json.loads(m.pop("peaks_json") or "[]")
    m["audio"] = bytes(m["audio"])
    return m


def recording_ids() -> set[int]:
    with engine().connect() as con:
        return {row[0] for row in con.execute(select(recordings.c.call_id))}


def recordings_size_mb() -> tuple[int, float]:
    from sqlalchemy import func
    with engine().connect() as con:
        n, size = con.execute(select(func.count(), func.coalesce(func.sum(func.length(recordings.c.audio)), 0))).one()
    return int(n), round(float(size) / 1e6, 1)


def delete_all_recordings() -> None:
    with engine().begin() as con:
        con.execute(delete(recordings))
        con.execute(update(calls).values(transcript_json=None))
    if not is_online_db():
        with engine().connect().execution_options(isolation_level="AUTOCOMMIT") as con:
            con.execute(text("VACUUM"))


def save_error(call_id: int, error: str) -> None:
    with engine().begin() as con:
        con.execute(update(calls).where(calls.c.id == call_id).values(status="error", error=error[:2000]))


def update_meta(call_id: int, **fields) -> None:
    allowed = {"executive", "mobile", "call_type", "call_date", "campaign", "pitch_version", "followup_done"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    with engine().begin() as con:
        con.execute(update(calls).where(calls.c.id == int(call_id)).values(**sets))


def delete_call(call_id: int) -> None:
    delete_calls([call_id])


def delete_calls(call_ids: list[int]) -> int:
    if not call_ids:
        return 0
    ids = [int(i) for i in call_ids]
    with engine().begin() as con:
        con.execute(delete(recordings).where(recordings.c.call_id.in_(ids)))
        return con.execute(delete(calls).where(calls.c.id.in_(ids))).rowcount


def delete_all(include_reports: bool = True) -> None:
    """Remove every stored review (and optionally every AI insights report)."""
    with engine().begin() as con:
        con.execute(delete(recordings))
        con.execute(delete(calls))
        if include_reports:
            con.execute(delete(reports))
    if not is_online_db():
        with engine().connect().execution_options(isolation_level="AUTOCOMMIT") as con:
            con.execute(text("VACUUM"))


def load_calls() -> pd.DataFrame:
    with engine().connect() as con:
        df = pd.read_sql_query(select(calls).order_by(calls.c.call_date.desc(), calls.c.id.desc()), con)
    df["review"] = df["review_json"].apply(lambda s: json.loads(s) if isinstance(s, str) and s else None)
    df["segments"] = df["transcript_json"].apply(lambda s: json.loads(s) if isinstance(s, str) and s else [])
    df["audio"] = df["audio_stats"].apply(lambda s: json.loads(s) if isinstance(s, str) and s else {})
    return df


def save_report(scope: str, content_md: str, data: dict | None = None, call_ids: list[int] | None = None) -> None:
    with engine().begin() as con:
        con.execute(insert(reports).values(created_at=_now(), scope=scope, content_md=content_md,
                                           content_json=json.dumps(data, ensure_ascii=False) if data else None,
                                           call_ids=json.dumps([int(i) for i in call_ids]) if call_ids else None))


def load_reports() -> list[dict]:
    with engine().connect() as con:
        out = [dict(r._mapping) for r in con.execute(select(reports).order_by(reports.c.id.desc()))]
    for r in out:
        r["data"] = json.loads(r["content_json"]) if r.get("content_json") else None
        r["ids"] = json.loads(r["call_ids"]) if r.get("call_ids") else []
    return out
