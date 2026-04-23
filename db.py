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

# DB 位置：環境變數優先（部署時指向 persistent volume）
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

CREATE TABLE IF NOT EXISTS extended_questions (
    id TEXT PRIMARY KEY,
    source_qid TEXT NOT NULL,
    stem TEXT NOT NULL,
    options_json TEXT NOT NULL,
    answer TEXT NOT NULL,
    explanation TEXT,
    concepts_json TEXT,
    category TEXT,
    subcategory TEXT,
    model TEXT,
    prompt_version TEXT,
    generated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_extq_source
    ON extended_questions(source_qid);
CREATE INDEX IF NOT EXISTS idx_extq_version
    ON extended_questions(prompt_version, source_qid);

CREATE TABLE IF NOT EXISTS verify_analyses (
    question_id TEXT PRIMARY KEY,
    official_answer TEXT NOT NULL,
    correct_logic TEXT,
    options_json TEXT,
    key_concepts_json TEXT,
    model TEXT,
    prompt_version TEXT,
    generated_at TEXT NOT NULL,
    core_concept TEXT DEFAULT '',
    citation TEXT DEFAULT '',
    framework TEXT DEFAULT '',
    exam_tips_json TEXT DEFAULT ''
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _connect() -> sqlite3.Connection:
    """開一條短連線，啟用 WAL + foreign keys。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """首次啟動時建表。重複呼叫安全。

    若偵測到舊版 schema(line_user_id 欄位),會 DROP 舊 users 表並以新
    schema(firebase_uid)重建。舊 profiles / events 也會連帶清空因為 user_id
    不再對得起來。只在從 LINE 遷移到 Firebase 的第一次啟動觸發。

    verify_analyses 表也會嘗試 ALTER 加上 v2 新欄位(core_concept, citation),
    舊資料庫不會壞,新欄位預設空字串。
    """
    global _initialized
    with _init_lock:
        if _initialized:
            return
        with _connect() as conn:
            _migrate_users_to_firebase(conn)
            conn.executescript(_SCHEMA)
            _ensure_verify_v2_columns(conn)
        _initialized = True
        logger.info("DB initialized at %s", DB_PATH)


def _ensure_verify_v2_columns(conn: sqlite3.Connection) -> None:
    """ALTER TABLE 加上 v2+ 新欄位(若已存在則跳過)。"""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(verify_analyses)")}
    for col in ("core_concept", "citation", "framework", "exam_tips_json"):
        if col not in cols:
            try:
                conn.execute(f"ALTER TABLE verify_analyses ADD COLUMN {col} TEXT DEFAULT ''")
                logger.info("verify_analyses: added column %s", col)
            except sqlite3.OperationalError as exc:
                logger.warning("verify_analyses: ALTER ADD %s 失敗: %s", col, exc)


def _migrate_users_to_firebase(conn: sqlite3.Connection) -> None:
    """若現有 users 表還是 line_user_id 欄位,砍掉重建。"""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    )
    if not cur.fetchone():
        return
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "firebase_uid" in cols:
        return
    if "line_user_id" not in cols:
        return
    logger.warning(
        "DB migration: 偵測到舊 users schema(line_user_id),DROP users/profiles/events 重建"
    )
    conn.execute("DROP TABLE IF EXISTS profiles")
    conn.execute("DROP TABLE IF EXISTS events")
    conn.execute("DROP TABLE IF EXISTS users")


# ---------- users ----------


def upsert_user(
    firebase_uid: str,
    display_name: str = "",
    picture_url: str = "",
    email: str = "",
) -> dict[str, Any]:
    """Firebase 驗證 token 成功後 upsert。回傳 user dict(含 id)。"""
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


def get_user(user_id: int) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


# ---------- profiles ----------


def load_profile(user_id: int) -> Optional[dict[str, Any]]:
    """載入 learningProfile；無則回 None。"""
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
    """整包覆寫 learningProfile。使用 UPSERT。"""
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


# ---------- events (analytics) ----------


def log_event(
    user_id: Optional[int],
    event_type: str,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """寫入 analytics 事件。失敗不中斷業務。"""
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


def count_events(
    event_type: Optional[str] = None,
    since: Optional[str] = None,
) -> int:
    with _connect() as conn:
        if event_type and since:
            cur = conn.execute(
                "SELECT COUNT(*) AS c FROM events WHERE event_type = ? AND created_at >= ?",
                (event_type, since),
            )
        elif event_type:
            cur = conn.execute(
                "SELECT COUNT(*) AS c FROM events WHERE event_type = ?",
                (event_type,),
            )
        else:
            cur = conn.execute("SELECT COUNT(*) AS c FROM events")
        return int(cur.fetchone()["c"])


# ---------- extended_questions (pre-computed AI 延伸題) ----------


def insert_extensions(rows: list[dict[str, Any]]) -> int:
    """批次寫入延伸題。rows 每筆需含：
    id, source_qid, stem, options(dict), answer, explanation,
    concepts(list), category, subcategory, model, prompt_version.
    """
    if not rows:
        return 0
    now = _now_iso()
    payload = [
        (
            r["id"],
            r["source_qid"],
            r["stem"],
            json.dumps(r.get("options") or {}, ensure_ascii=False),
            r["answer"],
            r.get("explanation", ""),
            json.dumps(r.get("concepts") or [], ensure_ascii=False),
            r.get("category", ""),
            r.get("subcategory", ""),
            r.get("model", ""),
            r.get("prompt_version", "v1"),
            now,
        )
        for r in rows
    ]
    with _connect() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO extended_questions
                (id, source_qid, stem, options_json, answer, explanation,
                 concepts_json, category, subcategory, model, prompt_version, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            payload,
        )
    return len(rows)


def get_extensions_by_source(source_qid: str, limit: int = 10) -> list[dict[str, Any]]:
    """讀取某考古題的預計算延伸題，format 成前端練習題 shape。"""
    with _connect() as conn:
        cur = conn.execute(
            """SELECT id, source_qid, stem, options_json, answer, explanation,
                      concepts_json, category, subcategory
                 FROM extended_questions
                 WHERE source_qid = ?
                 ORDER BY generated_at ASC
                 LIMIT ?""",
            (source_qid, limit),
        )
        out = []
        for row in cur.fetchall():
            try:
                opts = json.loads(row["options_json"])
                concepts = json.loads(row["concepts_json"] or "[]")
            except (json.JSONDecodeError, ValueError):
                continue
            out.append({
                "id": row["id"],
                "stem": row["stem"],
                "text": row["stem"],
                "question_text": row["stem"],
                "options": opts,
                "answer": row["answer"],
                "category": row["category"] or "延伸練習",
                "subcategory": row["subcategory"] or "",
                "concepts": concepts,
                "is_competency_based": False,
                "year": "AI",
                "city": "延伸",
                "subject": "",
                "is_ai_generated": True,
                "source_question_id": row["source_qid"],
                "ai_explanation": row["explanation"] or "",
            })
        return out


def count_extensions_grouped(prompt_version: str = "v1") -> dict[str, int]:
    """回傳 {source_qid: count} 給 bulk script 算 todo。"""
    with _connect() as conn:
        cur = conn.execute(
            """SELECT source_qid, COUNT(*) AS c
                 FROM extended_questions
                 WHERE prompt_version = ?
                 GROUP BY source_qid""",
            (prompt_version,),
        )
        return {row["source_qid"]: int(row["c"]) for row in cur.fetchall()}


def get_source_qid_for_extension(extension_id: str) -> Optional[str]:
    """給定延伸題的 id(例如 'ai_xxx', 'live_yyy', 'claude_sonnet_v1__107_臺北市_1__abc'),
    回傳其 source_qid。None 表示該 id 不是延伸題或不存在。"""
    if not extension_id:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT source_qid FROM extended_questions WHERE id = ?",
            (extension_id,),
        ).fetchone()
        if row:
            return row["source_qid"]
        return None


def get_verify_analysis(
    question_id: str,
    min_prompt_version: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """讀取某題的預計算 AI 解析。None 表示未 cache 或版本過舊。

    min_prompt_version:若給定,只回傳 prompt_version >= min_prompt_version 的
    cache。例如 'v2' 會把所有 v1 視為 cache miss → 觸發重生 → 自然淘汰舊資料。
    比較用字串排序(v10 在 v9 之後因為長度,但目前只有 v1/v2 不會踩到)。
    """
    with _connect() as conn:
        row = conn.execute(
            """SELECT question_id, official_answer, correct_logic,
                      options_json, key_concepts_json, prompt_version,
                      core_concept, citation, framework, exam_tips_json
                 FROM verify_analyses WHERE question_id = ?""",
            (question_id,),
        ).fetchone()
        if not row:
            return None
        # Version gating
        cached_ver = (row["prompt_version"] or "v1").strip()
        if min_prompt_version and cached_ver < min_prompt_version:
            return None
        try:
            exam_tips_str = row["exam_tips_json"] or ""
            exam_tips = json.loads(exam_tips_str) if exam_tips_str else []
            if not isinstance(exam_tips, list):
                exam_tips = []
            return {
                "question_id": row["question_id"],
                "official_answer": row["official_answer"],
                "core_concept": row["core_concept"] or "",
                "correct_logic": row["correct_logic"] or "",
                "options": json.loads(row["options_json"] or "[]"),
                "citation": row["citation"] or "",
                "framework": row["framework"] or "",
                "exam_tips": exam_tips,
                "key_concepts": json.loads(row["key_concepts_json"] or "[]"),
                "prompt_version": cached_ver,
                "error": "",
                "error_type": "",
            }
        except (json.JSONDecodeError, ValueError):
            return None


def upsert_verify_analysis(
    question_id: str,
    official_answer: str,
    correct_logic: str,
    options: list[dict[str, Any]],
    key_concepts: list[str],
    model: str = "",
    prompt_version: str = "v1",
    core_concept: str = "",
    citation: str = "",
    framework: str = "",
    exam_tips: Optional[list[str]] = None,
) -> None:
    """寫入或更新某題的 AI 解析快取。"""
    exam_tips_json = json.dumps(exam_tips or [], ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO verify_analyses
                (question_id, official_answer, correct_logic, options_json,
                 key_concepts_json, model, prompt_version, generated_at,
                 core_concept, citation, framework, exam_tips_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(question_id) DO UPDATE SET
                    correct_logic = excluded.correct_logic,
                    options_json = excluded.options_json,
                    key_concepts_json = excluded.key_concepts_json,
                    model = excluded.model,
                    prompt_version = excluded.prompt_version,
                    generated_at = excluded.generated_at,
                    core_concept = excluded.core_concept,
                    citation = excluded.citation,
                    framework = excluded.framework,
                    exam_tips_json = excluded.exam_tips_json""",
            (
                question_id,
                official_answer,
                correct_logic,
                json.dumps(options or [], ensure_ascii=False),
                json.dumps(key_concepts or [], ensure_ascii=False),
                model,
                prompt_version,
                _now_iso(),
                core_concept,
                citation,
                framework,
                exam_tips_json,
            ),
        )


def get_all_covered_source_qids() -> set[str]:
    """回傳所有至少有一題延伸題的 source_qid(不限 prompt_version)。

    scheduled 背景產題用 — 避免對已有 cache 的 source 重複產。
    """
    with _connect() as conn:
        cur = conn.execute(
            "SELECT DISTINCT source_qid FROM extended_questions WHERE source_qid IS NOT NULL"
        )
        return {row["source_qid"] for row in cur.fetchall()}


def export_all_extensions() -> list[dict[str, Any]]:
    """匯出整個 extended_questions 表為 list of dicts(保留 generated_at)。

    Seed file 工作流用:本機產題 → export → commit → Railway 部署時 import。
    """
    with _connect() as conn:
        cur = conn.execute(
            """SELECT id, source_qid, stem, options_json, answer, explanation,
                      concepts_json, category, subcategory, model,
                      prompt_version, generated_at
                 FROM extended_questions
                 ORDER BY generated_at ASC"""
        )
        out = []
        for row in cur.fetchall():
            try:
                options = json.loads(row["options_json"])
                concepts = json.loads(row["concepts_json"] or "[]")
            except (json.JSONDecodeError, ValueError):
                continue
            out.append({
                "id": row["id"],
                "source_qid": row["source_qid"],
                "stem": row["stem"],
                "options": options,
                "answer": row["answer"],
                "explanation": row["explanation"] or "",
                "concepts": concepts,
                "category": row["category"] or "",
                "subcategory": row["subcategory"] or "",
                "model": row["model"] or "",
                "prompt_version": row["prompt_version"] or "v1",
                "generated_at": row["generated_at"],
            })
        return out


def import_extensions_preserving_ts(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """從 seed file 匯入延伸題,**保留原始 generated_at**。

    INSERT OR IGNORE 語義:若 id 已存在則跳過(不會覆蓋 Railway 現有 rows)。
    回傳 (attempted, inserted) — inserted 是實際新增的筆數(扣掉已存在的)。
    """
    if not rows:
        return (0, 0)
    payload = []
    for r in rows:
        try:
            payload.append((
                r["id"],
                r["source_qid"],
                r["stem"],
                json.dumps(r.get("options") or {}, ensure_ascii=False),
                r["answer"],
                r.get("explanation", ""),
                json.dumps(r.get("concepts") or [], ensure_ascii=False),
                r.get("category", ""),
                r.get("subcategory", ""),
                r.get("model", ""),
                r.get("prompt_version", "v1"),
                r.get("generated_at") or _now_iso(),
            ))
        except (KeyError, TypeError):
            continue
    with _connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) AS c FROM extended_questions"
        ).fetchone()["c"]
        conn.executemany(
            """INSERT OR IGNORE INTO extended_questions
                (id, source_qid, stem, options_json, answer, explanation,
                 concepts_json, category, subcategory, model, prompt_version, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            payload,
        )
        after = conn.execute(
            "SELECT COUNT(*) AS c FROM extended_questions"
        ).fetchone()["c"]
    return (len(payload), after - before)


# ── 法警特考專用 helpers ──

def get_or_create_user(firebase_uid: str, email: str = "", name: str = "") -> dict:
    """main.py 用：取得或建立使用者，回傳 user dict。"""
    return upsert_user(firebase_uid, display_name=name, email=email)


def log_practice_event(uid: str, q_id: str, subject: str, is_correct: bool) -> None:
    """記錄使用者練習一題的結果。"""
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
    """以 firebase_uid 取得 profile dict。"""
    with _connect() as conn:
        cur = conn.execute("SELECT id FROM users WHERE firebase_uid = ?", (firebase_uid,))
        row = cur.fetchone()
        if not row:
            return None
        return load_profile(row["id"])
