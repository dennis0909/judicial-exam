"""SQLite 資料層 — users / profiles / events。

設計原則：
- 單檔 SQLite，讀寫都用短連線避免 lock
- WAL 模式，允許讀寫併發
- profile 用 JSON blob 存，schema 演進不需 migration
- events 用於 beta 測量（DAU、留存、功能使用）
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DB_PATH: Path = Path(os.environ.get("DB_PATH", "data/app.db"))

_init_lock = threading.Lock()
_initialized = False

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    firebase_uid TEXT UNIQUE NOT NULL,
    display_name TEXT,
    picture_url TEXT,
    email TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    event_type TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_user_time
    ON events(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_type_time
    ON events(event_type, created_at);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        with _connect() as conn:
            conn.executescript(_SCHEMA)
        _initialized = True
        logger.info("DB initialized at %s", DB_PATH)


# ---------- users ----------

def upsert_user(
    firebase_uid: str,
    display_name: str = "",
    picture_url: str = "",
    email: str = "",
) -> dict[str, Any]:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            "SELECT id, created_at FROM users WHERE firebase_uid = ?",
            (firebase_uid,),
        )
        row = cur.fetchone()
        if row:
            user_id = row["id"]
            conn.execute(
                """UPDATE users SET
                    display_name = ?, picture_url = ?, email = ?, last_login_at = ?
                    WHERE id = ?""",
                (display_name, picture_url, email, now, user_id),
            )
            created_at = row["created_at"]
        else:
            cur = conn.execute(
                """INSERT INTO users
                    (firebase_uid, display_name, picture_url, email, created_at, last_login_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                (firebase_uid, display_name, picture_url, email, now, now),
            )
            user_id = cur.lastrowid
            created_at = now

    return {
        "id": user_id,
        "firebase_uid": firebase_uid,
        "display_name": display_name,
        "picture_url": picture_url,
        "email": email,
        "created_at": created_at,
        "last_login_at": now,
    }


# ---------- profiles ----------

def load_profile(user_id: int) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT data, updated_at FROM profiles WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        try:
            data = json.loads(row["data"])
            data["_updated_at"] = row["updated_at"]
            return data
        except json.JSONDecodeError as exc:
            logger.warning("profile JSON 損毀 user_id=%s: %s", user_id, exc)
            return None


def save_profile(user_id: int, profile: dict[str, Any]) -> None:
    now = _now_iso()
    payload = json.dumps(profile, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO profiles (user_id, data, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at""",
            (user_id, payload, now),
        )


# ---------- events ----------

def log_event(
    user_id: Optional[int],
    event_type: str,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    try:
        blob = json.dumps(payload, ensure_ascii=False) if payload else None
        with _connect() as conn:
            conn.execute(
                """INSERT INTO events (user_id, event_type, payload, created_at)
                    VALUES (?, ?, ?, ?)""",
                (user_id, event_type, blob, _now_iso()),
            )
    except Exception as exc:
        logger.warning("log_event 失敗 [%s]: %s", event_type, exc)


# ---------- 法警特考專用 helpers ----------

def get_or_create_user(firebase_uid: str, email: str = "", name: str = "") -> dict:
    return upsert_user(firebase_uid, display_name=name, email=email)


def log_practice_event(uid: str, q_id: str, subject: str, is_correct: bool) -> None:
    with _connect() as conn:
        cur = conn.execute("SELECT id FROM users WHERE firebase_uid = ?", (uid,))
        row = cur.fetchone()
        if not row:
            return
        user_id = row["id"]
    log_event(user_id=user_id, event_type="practice", payload={
        "q_id": q_id, "subject": subject, "is_correct": is_correct,
    })


def get_profile(firebase_uid: str) -> Optional[dict]:
    with _connect() as conn:
        cur = conn.execute("SELECT id FROM users WHERE firebase_uid = ?", (firebase_uid,))
        row = cur.fetchone()
        if not row:
            return None
        return load_profile(row["id"])
