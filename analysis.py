"""Question enrichment and exam-point analysis helpers."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TAXONOMY_FILE = DATA_DIR / "topic_taxonomy.json"
AMENDMENTS_FILE = DATA_DIR / "amendments.json"
CURRENT_AFFAIRS_FILE = DATA_DIR / "current_affairs.json"


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_taxonomy() -> dict[str, Any]:
    return _load_json(TAXONOMY_FILE, {"subjects": {}})


@lru_cache(maxsize=1)
def load_amendments() -> dict[str, Any]:
    return _load_json(AMENDMENTS_FILE, {"items": [], "yearly_focus": []})


@lru_cache(maxsize=1)
def load_current_affairs() -> dict[str, Any]:
    return _load_json(CURRENT_AFFAIRS_FILE, {"items": [], "source_feeds": []})


def _text_for(q: dict[str, Any]) -> str:
    options = q.get("options") or {}
    opt_text = " ".join(str(v) for v in options.values())
    return f"{q.get('stem', '')} {opt_text}".lower()


def classify_question(q: dict[str, Any]) -> dict[str, Any]:
    """Return topic metadata for one question using weighted keyword matching."""
    taxonomy = load_taxonomy()
    subject = q.get("subject", "")
    subject_cfg = taxonomy.get("subjects", {}).get(subject, {})
    topics = subject_cfg.get("topics", [])

    if not topics:
        return {
            "topic_id": "uncategorized",
            "topic": "未分類",
            "score": 0,
            "concepts": [],
            "law_refs": [],
            "keywords": [],
        }

    text = _text_for(q)
    best: dict[str, Any] | None = None
    best_score = -1
    best_hits: list[str] = []

    for topic in topics:
        hits = []
        score = 0
        for kw in topic.get("keywords", []):
            kw_norm = str(kw).lower()
            if kw_norm and kw_norm in text:
                hits.append(str(kw))
                score += 2 if len(kw_norm) >= 4 else 1
        if score > best_score:
            best = topic
            best_score = score
            best_hits = hits

    if not best or best_score <= 0:
        best = topics[0]
        best_score = 0
        best_hits = []

    return {
        "topic_id": best.get("id", "uncategorized"),
        "topic": best.get("label", "未分類"),
        "score": best_score,
        "concepts": best.get("concepts", []),
        "law_refs": best.get("law_refs", []),
        "keywords": best_hits,
    }


def enrich_question(q: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(q)
    meta = classify_question(q)
    enriched.update({
        "topic_id": meta["topic_id"],
        "topic": meta["topic"],
        "concepts": meta["concepts"],
        "law_refs": meta["law_refs"],
        "topic_keywords": meta["keywords"],
    })
    return enriched


def build_question_indexes(questions: list[dict[str, Any]]) -> dict[str, Any]:
    enriched = [enrich_question(q) for q in questions]
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for q in enriched:
        by_topic[q["topic_id"]].append(q)
    return {
        "questions": enriched,
        "by_id": {q["id"]: q for q in enriched},
        "by_topic": dict(by_topic),
    }


def build_exam_point_stats(questions: list[dict[str, Any]]) -> dict[str, Any]:
    enriched = [enrich_question(q) for q in questions]
    topic_counter = Counter((q["topic_id"], q["topic"]) for q in enriched)
    subject_topic: dict[str, Counter] = defaultdict(Counter)
    year_topic: dict[int, Counter] = defaultdict(Counter)
    answer_counter: Counter[str] = Counter()

    for q in enriched:
        subject_topic[q.get("subject", "")][(q["topic_id"], q["topic"])] += 1
        if q.get("roc_year"):
            year_topic[int(q["roc_year"])][(q["topic_id"], q["topic"])] += 1
        if q.get("answer"):
            answer_counter[q["topic_id"]] += 1

    topics = []
    total = len(enriched) or 1
    for (topic_id, label), count in topic_counter.most_common():
        recent_count = sum(1 for q in enriched if q["topic_id"] == topic_id and int(q.get("roc_year") or 0) >= 112)
        answer_rate = answer_counter[topic_id] / count if count else 0
        topics.append({
            "topic_id": topic_id,
            "topic": label,
            "count": count,
            "share": round(count / total, 4),
            "recent_count": recent_count,
            "answer_rate": round(answer_rate, 3),
            "heat": round(count * 0.7 + recent_count * 1.4 + answer_rate * 8, 2),
        })

    by_subject = {}
    for subject, counter in subject_topic.items():
        by_subject[subject] = [
            {"topic_id": tid, "topic": label, "count": count}
            for (tid, label), count in counter.most_common()
        ]

    by_year = {}
    for year, counter in year_topic.items():
        by_year[str(year)] = [
            {"topic_id": tid, "topic": label, "count": count}
            for (tid, label), count in counter.most_common(8)
        ]

    return {
        "total_questions": len(enriched),
        "topics": sorted(topics, key=lambda x: x["heat"], reverse=True),
        "by_subject": by_subject,
        "by_year": dict(sorted(by_year.items())),
        "taxonomy": load_taxonomy(),
    }


def hot_questions(questions: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    enriched = [enrich_question(q) for q in questions]
    stats = build_exam_point_stats(questions)
    heat_by_topic = {t["topic_id"]: t["heat"] for t in stats["topics"]}
    max_year = max((int(q.get("roc_year") or 0) for q in questions), default=0)

    ranked = []
    for q in enriched:
        year = int(q.get("roc_year") or 0)
        recency = max(0, year - (max_year - 3))
        has_answer = 1 if q.get("answer") else 0
        keyword_bonus = min(len(q.get("topic_keywords") or []), 4)
        score = heat_by_topic.get(q["topic_id"], 0) + recency * 2 + has_answer * 3 + keyword_bonus
        ranked.append({
            "id": q["id"],
            "roc_year": q.get("roc_year"),
            "subject": q.get("subject"),
            "question_number": q.get("question_number"),
            "type": q.get("type"),
            "stem": q.get("stem"),
            "answer": q.get("answer"),
            "topic_id": q["topic_id"],
            "topic": q["topic"],
            "law_refs": q.get("law_refs", []),
            "heat_score": round(score, 2),
            "reason": _hot_reason(q, recency, has_answer, keyword_bonus),
        })
    return sorted(ranked, key=lambda x: x["heat_score"], reverse=True)[:limit]


def _hot_reason(q: dict[str, Any], recency: int, has_answer: int, keyword_bonus: int) -> str:
    bits = [f"歸入高頻考點「{q.get('topic', '未分類')}」"]
    if recency:
        bits.append("近年出現")
    if has_answer:
        bits.append("可直接練習與核對答案")
    if keyword_bonus:
        bits.append("題幹命中核心關鍵字")
    return "、".join(bits)


def generate_ai_analysis(q: dict[str, Any]) -> dict[str, Any]:
    """Deterministic AI-style analysis for offline use."""
    enriched = enrich_question(q)
    subject = enriched.get("subject", "")
    topic_id = enriched.get("topic_id", "")
    topic = enriched.get("topic", "未分類")
    stem = enriched.get("stem", "")
    amendments = _related_items(load_amendments().get("items", []), subject, topic_id, stem)
    affairs = _related_items(load_current_affairs().get("items", []), subject, topic_id, stem)

    law_refs = enriched.get("law_refs") or []
    concepts = enriched.get("concepts") or []
    answer = enriched.get("answer")

    return {
        "q_id": enriched.get("id"),
        "mode": "local-rule-analysis",
        "subject": subject,
        "topic": topic,
        "concepts": concepts,
        "law_refs": law_refs,
        "answer": answer,
        "core_issue": _core_issue(subject, topic, stem),
        "exam_strategy": _exam_strategy(enriched),
        "option_strategy": _option_strategy(enriched),
        "amendment_alerts": amendments[:3],
        "current_affairs_alerts": affairs[:3],
        "confidence": _confidence(enriched),
        "source_note": "本分析由本地考點分類、題幹關鍵字與修法/時事資料集產生；需精確法條內容時請回查官方來源。",
    }


def _related_items(items: list[dict[str, Any]], subject: str, topic_id: str, stem: str) -> list[dict[str, Any]]:
    stem_lower = stem.lower()
    related = []
    for item in items:
        subjects = set(item.get("subjects", []))
        topics = set(item.get("topic_ids", []))
        keywords = [str(k).lower() for k in item.get("keywords", [])]
        score = 0
        if subject in subjects:
            score += 2
        if topic_id in topics:
            score += 3
        score += sum(1 for kw in keywords if kw and kw in stem_lower)
        if score:
            compact = dict(item)
            compact["_score"] = score
            related.append(compact)
    return sorted(related, key=lambda x: x["_score"], reverse=True)


def _core_issue(subject: str, topic: str, stem: str) -> str:
    if subject == "行政法概要":
        return f"判斷行政行為是否符合「{topic}」及一般法律原則。"
    if subject == "刑法概要":
        return f"先定位構成要件、違法性與罪責，再處理「{topic}」。"
    if subject == "刑事訴訟法概要":
        return f"確認程序階段、強制處分權限與救濟路徑，核心為「{topic}」。"
    if subject == "法院組織法":
        return f"掌握法院/檢察機關組織、職權與法庭秩序，核心為「{topic}」。"
    if subject == "法學知識與英文":
        return f"連結憲法、法學緒論與英文閱讀，核心為「{topic}」。"
    return f"本題主要考「{topic}」。"


def _exam_strategy(q: dict[str, Any]) -> list[str]:
    strategies = []
    if q.get("type") == "mcq":
        strategies.append("先刪除與法條用語明顯不合的選項，再比較最精確的法律效果。")
    else:
        strategies.append("申論題先列爭點，再分要件、涵攝、結論。")
    if q.get("law_refs"):
        strategies.append("作答前回憶相關法條架構：" + "、".join(q["law_refs"][:4]))
    if q.get("topic_keywords"):
        strategies.append("題幹關鍵字：" + "、".join(q["topic_keywords"][:5]))
    return strategies


def _option_strategy(q: dict[str, Any]) -> list[str]:
    options = q.get("options") or {}
    if not options:
        return ["本題不是選擇題，建議以爭點清單整理答題架構。"]
    answer = q.get("answer")
    out = []
    for key in sorted(options):
        label = "正解候選" if answer and key == answer else "干擾選項"
        out.append(f"{key}: {label}，檢查是否符合「{q.get('topic')}」的要件與效果。")
    return out


def _confidence(q: dict[str, Any]) -> float:
    score = 0.45
    if q.get("topic_keywords"):
        score += min(len(q["topic_keywords"]) * 0.08, 0.25)
    if q.get("law_refs"):
        score += 0.15
    if q.get("answer"):
        score += 0.1
    return round(min(score, 0.92), 2)
