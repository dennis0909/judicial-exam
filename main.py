"""法警特考考古題分析系統 — FastAPI 後端"""

import json
import logging
import os
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from utils import normalize_subject, SUBJECTS, QUESTION_TYPE_DISPLAY
import auth_firebase as fb_auth
import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="法警特考考古題分析系統", version="1.0.0")
db.init_db()

# ---------- Load questions ----------
_ROOT = Path(__file__).parent
_Q_FILE = _ROOT / "questions.json"

with open(_Q_FILE, encoding="utf-8") as f:
    _data = json.load(f)

ALL_QUESTIONS: list[dict] = _data["questions"]
Q_BY_ID: dict[str, dict] = {q["id"]: q for q in ALL_QUESTIONS}
ALL_YEARS: list[int] = sorted({q["roc_year"] for q in ALL_QUESTIONS if q.get("roc_year")})

logger.info(f"載入 {len(ALL_QUESTIONS)} 題（{len(ALL_YEARS)} 年度）")


# ---------- Auth helpers ----------
async def _current_user(authorization: str | None) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        return fb_auth.verify_id_token(token)
    except Exception:
        return None


# ---------- /api/firebase-config ----------
@app.get("/api/firebase-config")
async def firebase_config():
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", ""),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", ""),
    }


# ---------- /api/me ----------
@app.get("/api/me")
async def me(authorization: Optional[str] = Header(default=None)):
    user = await _current_user(authorization)
    if not user:
        return {"authenticated": False}
    db_user = db.get_or_create_user(user["uid"], user.get("email", ""), user.get("name", ""))
    return {"authenticated": True, "uid": user["uid"], "name": user.get("name"), "email": user.get("email")}


# ---------- /api/subjects ----------
@app.get("/api/subjects")
async def get_subjects():
    counts = Counter(q["subject"] for q in ALL_QUESTIONS)
    return [
        {"subject": s, "count": counts.get(s, 0), "available": counts.get(s, 0) > 0}
        for s in SUBJECTS
    ]


# ---------- /api/years ----------
@app.get("/api/years")
async def get_years():
    year_subj = defaultdict(Counter)
    for q in ALL_QUESTIONS:
        if q.get("roc_year"):
            year_subj[q["roc_year"]][q["subject"]] += 1
    return [
        {"roc_year": y, "subjects": dict(year_subj[y]), "total": sum(year_subj[y].values())}
        for y in sorted(year_subj.keys(), reverse=True)
    ]


# ---------- /api/questions ----------
@app.get("/api/questions")
async def get_questions(
    subject: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    q_type: Optional[str] = Query(None, alias="type"),
    keyword: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    shuffle: bool = Query(False),
):
    qs = ALL_QUESTIONS

    if subject:
        canonical = normalize_subject(subject)
        qs = [q for q in qs if q["subject"] == canonical]

    if year:
        qs = [q for q in qs if q.get("roc_year") == year]

    if q_type in ("mcq", "essay"):
        qs = [q for q in qs if q["type"] == q_type]

    if keyword:
        kw = keyword.strip().lower()
        qs = [q for q in qs if kw in q.get("stem", "").lower()]

    if shuffle:
        qs = list(qs)
        random.shuffle(qs)

    total = len(qs)
    page = qs[offset: offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "questions": page}


# ---------- /api/questions/{q_id} ----------
@app.get("/api/questions/{q_id}")
async def get_question(q_id: str):
    q = Q_BY_ID.get(q_id)
    if not q:
        raise HTTPException(404, "題目不存在")
    return q


# ---------- /api/stats ----------
@app.get("/api/stats")
async def get_stats():
    total = len(ALL_QUESTIONS)
    by_subject = Counter(q["subject"] for q in ALL_QUESTIONS)
    by_type = Counter(q["type"] for q in ALL_QUESTIONS)
    by_year = Counter(q["roc_year"] for q in ALL_QUESTIONS if q.get("roc_year"))

    # 年度趨勢（各科）
    trend: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for q in ALL_QUESTIONS:
        if q.get("roc_year") and q["subject"]:
            trend[q["roc_year"]][q["subject"]] += 1

    return {
        "total": total,
        "subjects": dict(by_subject),
        "types": {QUESTION_TYPE_DISPLAY.get(k, k): v for k, v in by_type.items()},
        "years": dict(sorted(by_year.items())),
        "trend": {str(y): dict(v) for y, v in sorted(trend.items())},
        "years_range": [min(ALL_YEARS), max(ALL_YEARS)] if ALL_YEARS else [],
    }


# ---------- /api/practice/session ----------
@app.post("/api/practice/session")
async def create_practice_session(
    subject: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    count: int = Query(20, ge=5, le=100),
    q_type: str = Query("mcq"),
):
    """產生練習題組（選擇題優先，有答案的題目先）"""
    qs = [q for q in ALL_QUESTIONS if q["type"] == q_type]

    if subject:
        canonical = normalize_subject(subject)
        qs = [q for q in qs if q["subject"] == canonical]

    if year:
        qs = [q for q in qs if q.get("roc_year") == year]

    if not qs:
        raise HTTPException(404, "無符合條件的題目")

    random.shuffle(qs)
    session_qs = qs[:count]

    return {
        "count": len(session_qs),
        "subject": subject,
        "year": year,
        "questions": [
            {
                "id": q["id"],
                "stem": q["stem"],
                "options": q["options"],
                "type": q["type"],
                "subject": q["subject"],
                "roc_year": q["roc_year"],
                "answer": q.get("answer") if q["type"] == "essay" else None,
                "explanation": q.get("explanation") if q["type"] == "essay" else None,
            }
            for q in session_qs
        ],
    }


# ---------- /api/practice/check ----------
@app.post("/api/practice/check")
async def check_answer(
    q_id: str = Query(...),
    answer: str = Query(...),
    authorization: Optional[str] = Header(default=None),
):
    q = Q_BY_ID.get(q_id)
    if not q:
        raise HTTPException(404, "題目不存在")

    correct_answer = q.get("answer")
    if correct_answer is None:
        return {
            "q_id": q_id,
            "submitted": answer.upper(),
            "correct": None,
            "is_correct": None,
            "note": "此題答案尚未收錄（申論題或待補充）",
        }

    is_correct = answer.upper() == correct_answer.upper()

    # 記錄練習紀錄（已登入者）
    user = await _current_user(authorization)
    if user:
        db.log_practice_event(
            uid=user["uid"],
            q_id=q_id,
            subject=q.get("subject", ""),
            is_correct=is_correct,
        )

    return {
        "q_id": q_id,
        "submitted": answer.upper(),
        "correct": correct_answer,
        "is_correct": is_correct,
        "explanation": q.get("explanation"),
    }


# ---------- /api/profile ----------
@app.get("/api/profile")
async def get_profile(authorization: Optional[str] = Header(default=None)):
    user = await _current_user(authorization)
    if not user:
        raise HTTPException(401, "請先登入")
    profile = db.get_profile(user["uid"])
    return profile or {}


# ---------- Static files + SPA fallback ----------
app.mount("/static", StaticFiles(directory=str(_ROOT / "static")), name="static")


@app.get("/")
async def index():
    from fastapi.responses import FileResponse
    return FileResponse(str(_ROOT / "static" / "index.html"))


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    from fastapi.responses import FileResponse
    static_file = _ROOT / "static" / full_path
    if static_file.exists() and static_file.is_file():
        return FileResponse(str(static_file))
    return FileResponse(str(_ROOT / "static" / "index.html"))

if __name__ == "__main__":
    import uvicorn
    # default port 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
