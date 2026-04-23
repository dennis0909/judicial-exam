"""
adaptive_engine.py — 自適應學習引擎

幼教教師甄試考古題系統的核心自適應邏輯：
- 題目分層分類（基本認知 / 情境應用 / 舉一反三）
- 概念先備知識圖譜（含英文別名）
- 精熟度計算（準確率 + 時間衰減 + 難度加權）
- 間隔復習排程
- 智慧選題演算法（優先度 = 弱點 + 復習 + 頻率 + 先備缺漏）
- 先備知識檢查與層級晉升 / 降級判定
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from concept_drill import estimate_difficulty, _is_negative_question


# ---------------------------------------------------------------------------
# 1. classify_layer — 題目自動分層
# ---------------------------------------------------------------------------

def classify_layer(question: dict) -> int:
    """將題目自動分類為三層。

    Layer 1（基本認知）：低難度、非素養題、非反向題、概念數 <= 2、題幹 < 120 字
    Layer 3（舉一反三）：素養導向 OR 反向題 OR 概念數 > 3
    Layer 2（情境應用）：其餘
    """
    difficulty: int = estimate_difficulty(question)
    is_competency: bool = bool(question.get("is_competency_based", False))
    is_negative: bool = _is_negative_question(question.get("question_text", ""))
    concept_count: int = len(question.get("concepts", []))
    text_len: int = len(question.get("question_text", ""))

    # Layer 1 — 所有條件都要滿足
    if (
        difficulty == 1
        and not is_competency
        and not is_negative
        and concept_count <= 2
        and text_len < 120
    ):
        return 1

    # Layer 3 — 任一條件即成立
    if is_competency or is_negative or concept_count > 3:
        return 3

    # Layer 2 — 其餘
    return 2


# ---------------------------------------------------------------------------
# 2. PREREQUISITE_GRAPH — 概念先備知識圖譜
# ---------------------------------------------------------------------------

PREREQUISITE_GRAPH: dict[str, list[str]] = {
    # ── Path A：發展心理學 ──────────────────────────────────
    "認知發展": ["發展基本概念"],
    "社會發展": ["發展基本概念"],
    "情緒發展": ["發展基本概念"],
    "語言發展": ["發展基本概念"],
    "動作發展": ["發展基本概念"],
    "道德發展": ["發展基本概念", "認知發展"],
    "皮亞傑": ["認知發展"],
    "維高斯基": ["認知發展", "社會發展"],
    "艾瑞克森": ["社會發展", "情緒發展"],
    "訊息處理": ["認知發展"],
    "保留概念": ["皮亞傑"],
    "物體恆存": ["皮亞傑"],
    "自我中心": ["皮亞傑"],
    "鷹架理論": ["維高斯基"],
    "近側發展區": ["維高斯基"],
    "記憶發展": ["訊息處理"],
    "注意力發展": ["訊息處理"],
    "後設認知": ["訊息處理", "認知發展"],
    "依附理論": ["社會發展", "情緒發展"],
    "氣質": ["發展基本概念"],
    "遊戲發展": ["認知發展", "社會發展"],
    "Piaget": ["認知發展"],
    "Vygotsky": ["認知發展", "社會發展"],
    "Erikson": ["社會發展", "情緒發展"],
    "Bruner": ["認知發展"],
    "Bandura": ["社會發展"],
    "Bronfenbrenner": ["發展基本概念"],

    # ── Path B：課程與教學 ──────────────────────────────────
    "課程模式": ["教保思潮"],
    "蒙特梭利": ["教保思潮", "課程模式"],
    "華德福": ["教保思潮", "課程模式"],
    "方案教學": ["課程模式"],
    "主題教學": ["課程模式"],
    "高瞻課程": ["課程模式"],
    "角落教學": ["課程模式"],
    "課程大綱": ["課程模式"],
    "學習區": ["課程大綱"],
    "統整性教學": ["課程大綱"],
    "幼兒園教保活動課程大綱": ["課程大綱"],
    "教學評量": ["課程大綱"],
    "檔案評量": ["教學評量"],
    "真實評量": ["教學評量"],
    "形成性評量": ["教學評量"],
    "總結性評量": ["教學評量"],
    "課程設計": ["課程模式", "課程大綱"],
    "教學策略": ["課程設計"],
    "Montessori": ["教保思潮", "課程模式"],
    "Reggio": ["教保思潮", "課程模式"],

    # ── Path C：法規與制度 ──────────────────────────────────
    "教保服務": ["幼兒教育及照顧法"],
    "設施設備": ["幼兒教育及照顧法"],
    "教保服務人員": ["幼兒教育及照顧法"],
    "幼兒園行政": ["幼兒教育及照顧法"],
    "師生比": ["幼兒教育及照顧法", "教保服務"],
    "評鑑": ["幼兒園行政"],
    "特殊教育": ["幼兒教育及照顧法"],
    "融合教育": ["特殊教育"],
    "個別化教育計畫": ["特殊教育", "融合教育"],
    "兒童權利公約": ["幼兒教育及照顧法"],

    # ── Cross paths：輔導與經營 ────────────────────────────
    "幼兒輔導": ["發展基本概念", "課程模式"],
    "行為輔導": ["幼兒輔導"],
    "正向管教": ["幼兒輔導", "班級經營"],
    "班級經營": ["發展基本概念", "課程模式"],
    "常規建立": ["班級經營"],
    "親師溝通": ["班級經營"],
    "學習環境規劃": ["班級經營", "學習區"],

    # ── 其他重要概念 ────────────────────────────────────────
    "幼兒健康": ["發展基本概念"],
    "幼兒安全": ["幼兒健康"],
    "營養與飲食": ["幼兒健康"],
    "多元文化教育": ["課程大綱"],
    "性別平等教育": ["課程大綱"],
    "美感教育": ["課程大綱"],
    "創造力": ["認知發展", "課程大綱"],
    "閱讀指導": ["語言發展", "課程大綱"],
    "幼小銜接": ["課程大綱", "發展基本概念"],
}


# ---------------------------------------------------------------------------
# 3. calculate_mastery — 精熟度計算
# ---------------------------------------------------------------------------

def calculate_mastery(concept_data: dict) -> float:
    """計算單一概念的精熟度分數（0.0 ~ 1.0）。

    公式：mastery = base_accuracy * 0.6 + recency_weight * 0.25 + difficulty_bonus * 0.15

    Parameters
    ----------
    concept_data : dict
        {
            "correct": int,           # 答對次數
            "total": int,             # 作答總次數
            "last_practiced": str,    # ISO-8601 日期字串（如 "2026-04-10"）
            "difficulty_sum_correct": float,  # 答對題目的難度總和
        }
    """
    correct: int = concept_data.get("correct", 0)
    total: int = concept_data.get("total", 0)
    last_practiced: str | None = concept_data.get("last_practiced")
    difficulty_sum_correct: float = concept_data.get("difficulty_sum_correct", 0.0)

    # base_accuracy
    base_accuracy: float = correct / total if total > 0 else 0.0

    # recency_weight — 指數衰減，距今天數越多權重越低
    if last_practiced:
        try:
            last_dt = datetime.fromisoformat(last_practiced)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days_since: float = max((now - last_dt).total_seconds() / 86400, 0.0)
        except (ValueError, TypeError):
            days_since = 30.0  # 無法解析則預設 30 天
    else:
        days_since = 30.0  # 從未練習

    recency_weight: float = min(math.exp(-days_since * 0.1), 1.0)

    # difficulty_bonus
    avg_diff: float = (difficulty_sum_correct / correct) if correct > 0 else 0.0
    difficulty_bonus: float = avg_diff / 3.0

    mastery: float = base_accuracy * 0.6 + recency_weight * 0.25 + difficulty_bonus * 0.15
    return round(min(max(mastery, 0.0), 1.0), 4)


# ---------------------------------------------------------------------------
# 4. get_review_interval — 間隔復習排程
# ---------------------------------------------------------------------------

def get_review_interval(mastery: float) -> int:
    """根據精熟度回傳建議復習間隔（天數）。

    | mastery   | interval |
    |-----------|----------|
    | 0 – 0.3   | 0（同次練習）|
    | 0.3 – 0.5 | 1        |
    | 0.5 – 0.7 | 3        |
    | 0.7 – 0.85| 7        |
    | 0.85+     | 14       |
    """
    if mastery < 0.3:
        return 0
    if mastery < 0.5:
        return 1
    if mastery < 0.7:
        return 3
    if mastery < 0.85:
        return 7
    return 14


# ---------------------------------------------------------------------------
# 5. select_next_questions — 智慧選題
# ---------------------------------------------------------------------------

def _build_concept_index(all_questions: list[dict]) -> dict[str, int]:
    """統計每個概念在題庫中出現的次數。"""
    index: dict[str, int] = {}
    for q in all_questions:
        for c in q.get("concepts", []):
            index[c] = index.get(c, 0) + 1
    return index


def select_next_questions(
    profile_summary: dict,
    all_questions: list[dict],
    q_by_id: dict[str, dict],
    count: int = 5,
) -> dict:
    """根據學習者狀態從題庫中挑選最適合的下一批題目。

    Parameters
    ----------
    profile_summary : dict
        包含 conceptMastery, recentQuestionIds, mode, count
    all_questions : list[dict]
        完整題庫
    q_by_id : dict[str, dict]
        以題目 id 為 key 的快速查詢表
    count : int
        要回傳的題數（預設 5）

    Returns
    -------
    dict
        { questions, reasoning, currentLayer, targetConcepts }
    """
    concept_mastery: dict[str, float] = profile_summary.get("conceptMastery", {})
    recent_ids: set[str] = set(profile_summary.get("recentQuestionIds", []))
    mode: str = profile_summary.get("mode", "adaptive")
    requested_count: int = profile_summary.get("count", count)

    concept_index: dict[str, int] = _build_concept_index(all_questions)
    max_concept_count: int = max(concept_index.values()) if concept_index else 1

    # 為每題計算優先度
    scored: list[tuple[float, dict]] = []

    for q in all_questions:
        qid: str = q.get("id", "")
        if qid in recent_ids:
            continue

        concepts: list[str] = q.get("concepts", [])
        if not concepts:
            avg_mastery = 0.5
        else:
            avg_mastery = sum(concept_mastery.get(c, 0.0) for c in concepts) / len(concepts)

        # (1 - mastery) * 40：越不熟的越優先
        weakness_score: float = (1.0 - avg_mastery) * 40.0

        # is_due_for_review * 30：到期復習加分
        review_score: float = 0.0
        for c in concepts:
            m = concept_mastery.get(c, 0.0)
            interval = get_review_interval(m)
            if interval == 0:
                review_score = 30.0
                break

        # exam_frequency * 15：高頻考點加分
        if concepts:
            freq = sum(concept_index.get(c, 0) for c in concepts) / len(concepts)
        else:
            freq = 0.0
        frequency_score: float = (freq / max_concept_count) * 15.0

        # prerequisite_failure * 10：先備知識缺漏加分
        prereq_score: float = 0.0
        for c in concepts:
            prereqs = PREREQUISITE_GRAPH.get(c, [])
            for p in prereqs:
                if concept_mastery.get(p, 0.0) < 0.3:
                    prereq_score = 10.0
                    break
            if prereq_score > 0:
                break

        priority: float = weakness_score + review_score + frequency_score + prereq_score

        # mode 調整
        if mode == "weakness":
            priority += weakness_score * 0.5  # 額外加重弱點
        elif mode == "review":
            priority += review_score * 0.5  # 額外加重復習

        scored.append((priority, q))

    # 按優先度排序，取前 N
    scored.sort(key=lambda x: x[0], reverse=True)
    selected: list[dict] = []
    for _priority, q in scored[:requested_count]:
        enriched = dict(q)
        enriched["layer"] = classify_layer(q)
        enriched["difficulty"] = estimate_difficulty(q)
        selected.append(enriched)

    # 分析結果
    target_concepts: list[str] = []
    seen_concepts: set[str] = set()
    for q in selected:
        for c in q.get("concepts", []):
            if c not in seen_concepts:
                seen_concepts.add(c)
                target_concepts.append(c)

    layers = [q.get("layer", 2) for q in selected]
    current_layer: int = round(sum(layers) / len(layers)) if layers else 1

    # 生成推薦理由
    weak_concepts = sorted(
        [(c, m) for c, m in concept_mastery.items() if m < 0.5],
        key=lambda x: x[1],
    )[:3]
    if weak_concepts:
        weak_names = "、".join(c for c, _ in weak_concepts)
        reasoning = f"根據你的學習紀錄，{weak_names}等概念尚需加強，本次選題以這些弱點為主。"
    else:
        reasoning = "你的整體表現不錯，本次選題兼顧復習與進階挑戰。"

    return {
        "questions": selected,
        "reasoning": reasoning,
        "currentLayer": current_layer,
        "targetConcepts": target_concepts[:10],
    }


# ---------------------------------------------------------------------------
# 6. check_prerequisites — 先備知識遞迴檢查
# ---------------------------------------------------------------------------

def check_prerequisites(
    concept: str,
    mastery_scores: dict[str, float],
) -> list[dict[str, Any]]:
    """遞迴檢查指定概念的所有先備知識。

    回傳精熟度低於 0.7 的先備概念清單，依深度優先遍歷。

    Parameters
    ----------
    concept : str
        使用者正在練習 / 遇到困難的概念
    mastery_scores : dict[str, float]
        各概念的精熟度分數

    Returns
    -------
    list[dict]
        [{ "concept": str, "mastery": float, "needs_review": bool }, ...]
    """
    result: list[dict[str, Any]] = []
    visited: set[str] = set()

    def _walk(c: str) -> None:
        if c in visited:
            return
        visited.add(c)

        prereqs: list[str] = PREREQUISITE_GRAPH.get(c, [])
        for p in prereqs:
            _walk(p)  # 先遞迴到更底層
            m = mastery_scores.get(p, 0.0)
            if m < 0.7 and p not in {r["concept"] for r in result}:
                result.append({
                    "concept": p,
                    "mastery": round(m, 4),
                    "needs_review": m < 0.3,
                })

    _walk(concept)
    return result


# ---------------------------------------------------------------------------
# 7. get_layer_progression — 層級晉升 / 降級判定
# ---------------------------------------------------------------------------

def get_layer_progression(
    concept: str,
    layer_progress: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """判斷某概念目前應處於哪一層，以及是否可晉升或需降級。

    Parameters
    ----------
    concept : str
        概念名稱
    layer_progress : dict
        {
            "recognition":  {"done": int, "correct": int},
            "application":  {"done": int, "correct": int},
            "transfer":     {"done": int, "correct": int},
        }

    Returns
    -------
    dict
        { "current_layer": 1|2|3, "can_advance": bool, "should_demote": bool, "message": str }

    晉升規則
    --------
    - L1 → L2：recognition correct_rate >= 0.7 AND done >= 3
    - L2 → L3：application correct_rate >= 0.6 AND done >= 3

    降級規則
    --------
    - L2 → L1：recognition done >= 3 但 application 連錯 3 題（correct_rate 過低）
    - L3 → L2：transfer 連錯 2 題
    """
    recog: dict[str, int] = layer_progress.get("recognition", {"done": 0, "correct": 0})
    app: dict[str, int] = layer_progress.get("application", {"done": 0, "correct": 0})
    trans: dict[str, int] = layer_progress.get("transfer", {"done": 0, "correct": 0})

    recog_done: int = recog.get("done", 0)
    recog_correct: int = recog.get("correct", 0)
    recog_rate: float = recog_correct / recog_done if recog_done > 0 else 0.0

    app_done: int = app.get("done", 0)
    app_correct: int = app.get("correct", 0)
    app_rate: float = app_correct / app_done if app_done > 0 else 0.0

    trans_done: int = trans.get("done", 0)
    trans_correct: int = trans.get("correct", 0)
    trans_rate: float = trans_correct / trans_done if trans_done > 0 else 0.0

    # --- 判斷目前層級 ---

    # 先判斷是否在 L3
    can_reach_l2: bool = recog_done >= 3 and recog_rate >= 0.7
    can_reach_l3: bool = can_reach_l2 and app_done >= 3 and app_rate >= 0.6

    if can_reach_l3 and trans_done > 0:
        # 在 L3 活動中
        # 降級檢查：最近 2 題都錯（trans_done >= 2 且最後 2 題答錯）
        consecutive_wrong_l3: int = trans_done - trans_correct  # 簡化：錯題數
        should_demote_l3: bool = (
            trans_done >= 2
            and consecutive_wrong_l3 >= 2
            and trans_rate < 0.5
        )
        if should_demote_l3:
            return {
                "current_layer": 3,
                "can_advance": False,
                "should_demote": True,
                "message": f"「{concept}」在舉一反三層連續答錯，建議退回情境應用層鞏固。",
            }
        return {
            "current_layer": 3,
            "can_advance": False,  # L3 已是最高層
            "should_demote": False,
            "message": f"「{concept}」已達舉一反三層，繼續挑戰！正確率 {trans_rate:.0%}",
        }

    if can_reach_l2:
        # 在 L2 或可晉升至 L3
        if app_done == 0:
            # 剛晉升到 L2，還沒作答
            return {
                "current_layer": 2,
                "can_advance": False,
                "should_demote": False,
                "message": f"「{concept}」已達情境應用層，開始挑戰情境題吧！",
            }

        # 降級檢查：連錯 3 題
        consecutive_wrong_l2: int = app_done - app_correct
        should_demote_l2: bool = (
            app_done >= 3
            and consecutive_wrong_l2 >= 3
            and app_rate < 0.4
        )
        if should_demote_l2:
            return {
                "current_layer": 2,
                "can_advance": False,
                "should_demote": True,
                "message": f"「{concept}」在情境應用層連續答錯，建議退回基本認知層複習。",
            }

        can_advance_to_l3: bool = app_done >= 3 and app_rate >= 0.6
        if can_advance_to_l3:
            return {
                "current_layer": 2,
                "can_advance": True,
                "should_demote": False,
                "message": f"「{concept}」情境應用層表現優異（{app_rate:.0%}），可以挑戰舉一反三層！",
            }

        return {
            "current_layer": 2,
            "can_advance": False,
            "should_demote": False,
            "message": f"「{concept}」情境應用層練習中，正確率 {app_rate:.0%}，再加油！",
        }

    # 在 L1
    can_advance_to_l2: bool = recog_done >= 3 and recog_rate >= 0.7
    if can_advance_to_l2:
        return {
            "current_layer": 1,
            "can_advance": True,
            "should_demote": False,
            "message": f"「{concept}」基本認知層表現優異（{recog_rate:.0%}），可以進入情境應用層！",
        }

    if recog_done == 0:
        return {
            "current_layer": 1,
            "can_advance": False,
            "should_demote": False,
            "message": f"「{concept}」尚未開始練習，從基本認知層開始吧！",
        }

    return {
        "current_layer": 1,
        "can_advance": False,
        "should_demote": False,
        "message": f"「{concept}」基本認知層練習中，正確率 {recog_rate:.0%}，繼續努力！",
    }
