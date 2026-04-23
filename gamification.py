from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from collections import Counter, defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# 科目 → 概念對照表
# ---------------------------------------------------------------------------

CATEGORY_CONCEPTS: dict[str, list[str]] = {
    "幼兒發展與輔導": [
        "皮亞傑認知發展論",
        "維高斯基社會文化論",
        "艾瑞克森心理社會發展",
        "布朗芬布倫生態系統論",
        "依附理論",
        "道德發展理論",
        "語言發展理論",
        "情緒發展",
        "社會發展",
        "感覺統合",
        "粗大動作發展",
        "精細動作發展",
        "認知發展評估",
        "行為改變技術",
        "遊戲理論",
        "自我概念發展",
        "氣質理論",
        "同儕關係發展",
        "家庭對發展的影響",
        "發展遲緩早期介入",
    ],
    "幼兒教保概論": [
        "幼兒教育史",
        "福祿貝爾教育哲學",
        "蒙特梭利教育法",
        "杜威進步主義教育",
        "幼兒園評鑑制度",
        "教保服務人員法規",
        "幼兒園行政管理",
        "親師溝通策略",
        "幼兒教育政策",
        "托育服務體系",
        "幼兒權利公約",
        "教保倫理",
        "班級經營策略",
        "學習環境規劃",
        "安全與健康管理",
        "多元文化教育",
        "性別平等教育",
        "幼兒觀察與記錄",
        "檔案評量",
        "親職教育",
    ],
    "教保課程與活動設計": [
        "幼兒園課程總綱",
        "六大領域課程",
        "主題統整課程",
        "方案課程",
        "角落學習",
        "學習區規劃",
        "課程目標設定",
        "學習活動設計",
        "語文領域教學",
        "數學領域教學",
        "自然科學探索",
        "藝術領域教學",
        "身體動作教學",
        "社會領域教學",
        "故事與繪本教學",
        "音樂律動教學",
        "戶外教學設計",
        "教學媒材運用",
        "差異化教學",
        "形成性評量",
    ],
    "特殊幼兒教育": [
        "特殊教育法規",
        "個別化教育計畫（IEP）",
        "融合教育理念",
        "自閉症類群障礙",
        "注意力不足過動症（ADHD）",
        "智能發展遲緩",
        "語言障礙",
        "聽覺障礙",
        "視覺障礙",
        "肢體障礙",
        "情緒行為障礙",
        "學習障礙",
        "早療評估工具",
        "輔助科技應用",
        "轉銜服務",
        "行為功能分析",
        "應用行為分析（ABA）",
        "感覺處理障礙",
        "資優幼兒教育",
        "特殊幼兒家庭支持",
    ],
    "幼兒保育": [
        "嬰幼兒營養與飲食",
        "幼兒健康管理",
        "常見幼兒疾病",
        "傳染病預防控制",
        "幼兒急救處理",
        "預防接種計畫",
        "環境衛生管理",
        "食品安全管理",
        "幼兒安全防護",
        "兒童虐待辨識",
        "強制通報制度",
        "嬰幼兒睡眠安全",
        "生長發育評估",
        "幼兒身心健康促進",
        "口腔保健",
        "視力保健",
        "過敏與氣喘管理",
        "特殊飲食需求",
        "人體工學與幼兒家具",
        "災害應變計畫",
    ],
}

# 所有概念 → 所屬科目的反查表（供 badge 計算使用）
_CONCEPT_TO_CATEGORY: dict[str, str] = {
    concept: cat
    for cat, concepts in CATEGORY_CONCEPTS.items()
    for concept in concepts
}


# ---------------------------------------------------------------------------
# 內部輔助函式
# ---------------------------------------------------------------------------

def _get_iso_week(date_str: str) -> str:
    """將 YYYY-MM-DD 轉換為 ISO 週字串，例如 '2026-W15'。"""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _date_from_str(date_str: str) -> date:
    """將 YYYY-MM-DD 字串轉為 date 物件。"""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _today() -> date:
    """取得今天日期（方便測試時替換）。"""
    return date.today()


# ---------------------------------------------------------------------------
# 1. calculate_streak
# ---------------------------------------------------------------------------

def calculate_streak(sessions: list[dict]) -> dict:
    """
    計算練習連續天數（streak）。

    每天至少作答 5 題才算有效練習日。

    Parameters
    ----------
    sessions : list[dict]
        前端傳入的練習記錄，格式：
        [{"date": "2026-04-12", "questionsAttempted": 25, "correctRate": 0.68}, ...]

    Returns
    -------
    dict
        {
            "current_streak": int,
            "longest_streak": int,
            "last_practice_date": str | None,
            "is_active_today": bool
        }
    """
    MIN_QUESTIONS = 5

    # 過濾有效練習日，並依日期去重（同日多次只算一天）
    valid_dates: set[date] = set()
    for s in sessions:
        if s.get("questionsAttempted", 0) >= MIN_QUESTIONS:
            try:
                valid_dates.add(_date_from_str(s["date"]))
            except (KeyError, ValueError):
                continue

    if not valid_dates:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "last_practice_date": None,
            "is_active_today": False,
        }

    sorted_dates = sorted(valid_dates)
    today = _today()

    # 計算最長連續天數
    longest = 1
    current_run = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            current_run += 1
            longest = max(longest, current_run)
        else:
            current_run = 1
    longest = max(longest, current_run)

    # 計算當前連續天數（從今天或昨天往回數）
    last_date = sorted_dates[-1]
    days_since_last = (today - last_date).days

    if days_since_last > 1:
        # 超過一天沒練習，streak 中斷
        current_streak = 0
    else:
        # 從最後練習日往回計算連續天數
        current_streak = 1
        check = last_date - timedelta(days=1)
        while check in valid_dates:
            current_streak += 1
            check -= timedelta(days=1)

    is_active_today = today in valid_dates
    last_practice_str = last_date.strftime("%Y-%m-%d")

    return {
        "current_streak": current_streak,
        "longest_streak": longest,
        "last_practice_date": last_practice_str,
        "is_active_today": is_active_today,
    }


# ---------------------------------------------------------------------------
# 2. calculate_badges
# ---------------------------------------------------------------------------

def calculate_badges(
    concept_mastery: dict,
    total_answered: int,
    streak: dict,
) -> list[dict]:
    """
    根據學習資料計算已獲得的成就徽章。

    Parameters
    ----------
    concept_mastery : dict
        概念精熟度資料，格式：
        {"皮亞傑": {"masteryScore": 0.72, "total": 12,
                    "layerProgress": {
                        "recognition": {"done": 5, "correct": 4},
                        "application": {"done": 3, "correct": 2},
                        "transfer": {"done": 0, "correct": 0}
                    }}, ...}
    total_answered : int
        累計作答題數。
    streak : dict
        由 calculate_streak() 回傳的連續天數資料。

    Returns
    -------
    list[dict]
        已獲得的徽章列表，每個元素格式：
        {"id": str, "name": str, "icon": str, "earned": True}
    """
    earned: list[dict] = []

    def _badge(badge_id: str, name: str, icon: str) -> dict:
        return {"id": badge_id, "name": name, "icon": icon, "earned": True}

    # --- 題數徽章 ---
    if total_answered >= 10:
        earned.append(_badge("first_10", "初試啼聲", "🌱"))
    if total_answered >= 100:
        earned.append(_badge("first_100", "百題達人", "🌿"))
    if total_answered >= 500:
        earned.append(_badge("first_500", "五百題勇者", "🌳"))

    # --- 連續天數徽章 ---
    current_streak = streak.get("current_streak", 0)
    if current_streak >= 7:
        earned.append(_badge("streak_7", "七日不懈", "🔥"))
    if current_streak >= 30:
        earned.append(_badge("streak_30", "月練達人", "💪"))

    # --- 概念精熟徽章 ---
    for concept, data in concept_mastery.items():
        mastery = data.get("masteryScore", 0.0)
        layer = data.get("layerProgress", {})
        transfer = layer.get("transfer", {})
        transfer_done = transfer.get("done", 0)
        transfer_correct = transfer.get("correct", 0)

        if mastery >= 0.9 and transfer_done >= 1 and transfer_correct >= 1:
            badge_id = f"concept_master_{concept}"
            earned.append(_badge(badge_id, f"{concept}精熟", "⭐"))

    # --- 科目達人徽章 ---
    # 計算每個科目中精熟概念比例（masteryScore >= 0.7）
    mastered_by_cat: dict[str, int] = defaultdict(int)
    touched_by_cat: dict[str, int] = defaultdict(int)

    for concept in concept_mastery:
        cat = _CONCEPT_TO_CATEGORY.get(concept)
        if cat is None:
            continue
        touched_by_cat[cat] += 1
        if concept_mastery[concept].get("masteryScore", 0.0) >= 0.7:
            mastered_by_cat[cat] += 1

    all_cats_mastered = True
    for cat, total_in_cat in CATEGORY_CONCEPTS.items():
        total_count = len(total_in_cat)
        mastered = mastered_by_cat.get(cat, 0)
        # 該科目至少有一題被觸及，且 80% 概念精熟
        if total_count > 0 and mastered / total_count >= 0.8:
            safe_cat = cat.replace(" ", "_")
            earned.append(_badge(f"category_master_{safe_cat}", f"{cat}達人", "🏆"))
        else:
            all_cats_mastered = False

    # --- 全科制霸 ---
    if all_cats_mastered:
        earned.append(_badge("all_master", "全科制霸", "👑"))

    return earned


# ---------------------------------------------------------------------------
# 3. generate_weekly_challenge
# ---------------------------------------------------------------------------

def generate_weekly_challenge(
    concept_mastery: dict,
    all_questions: list[dict],
    q_by_id: dict,
    recent_ids: set[str],
) -> dict:
    """
    生成本週挑戰題組（共 20 題）。

    題目組成：
    - 10 題：弱點概念（mastery < 0.5，取前 5 個最弱概念，各 2 題）
    - 5 題：複習到期（mastery 0.5–0.8，距上次練習 >= 3 天）
    - 5 題：全新概念（尚未出現在 concept_mastery 中）

    若某類別題目不足，從其他類別補足。

    Parameters
    ----------
    concept_mastery : dict
        概念精熟度資料（同 calculate_badges）。
    all_questions : list[dict]
        所有題目清單，每題需含 "id" 與 "concepts"（list[str]）欄位。
    q_by_id : dict
        題目 id → 題目 dict 的查詢表。
    recent_ids : set[str]
        最近已作答過的題目 id 集合（用於避免重複）。

    Returns
    -------
    dict
        {
            "week": "2026-W15",
            "questions": [...],
            "composition": {"weakness": int, "review": int, "new": int},
            "target_concepts": [...]
        }
    """
    today = _today()
    today_str = today.strftime("%Y-%m-%d")
    week_str = _get_iso_week(today_str)

    # ---------- 分類概念 ----------
    weak_concepts: list[tuple[str, float]] = []      # mastery < 0.5
    review_concepts: list[str] = []                  # 0.5 <= mastery < 0.8，3+ 天未練
    all_touched = set(concept_mastery.keys())

    for concept, data in concept_mastery.items():
        mastery = data.get("masteryScore", 0.0)
        last_practiced = data.get("lastPracticed")  # 可能不存在

        if mastery < 0.5:
            weak_concepts.append((concept, mastery))
        elif mastery < 0.8:
            due = True
            if last_practiced:
                try:
                    days_ago = (today - _date_from_str(last_practiced)).days
                    due = days_ago >= 3
                except ValueError:
                    pass
            if due:
                review_concepts.append(concept)

    # 弱點概念依精熟度由低到高，取前 5
    weak_concepts.sort(key=lambda x: x[1])
    top_weak = [c for c, _ in weak_concepts[:5]]

    # 找出全新概念（尚未觸及）
    all_known_concepts: set[str] = set()
    for concepts in CATEGORY_CONCEPTS.values():
        all_known_concepts.update(concepts)
    new_concepts = list(all_known_concepts - all_touched)

    # ---------- 依概念建立題目索引 ----------
    def questions_for_concepts(concept_list: list[str], exclude: set[str]) -> list[dict]:
        """取得屬於指定概念清單、且不在 exclude 中的題目。"""
        result: list[dict] = []
        seen: set[str] = set()
        for q in all_questions:
            qid = q.get("id", "")
            if qid in exclude or qid in seen:
                continue
            q_concepts = q.get("concepts", [])
            if any(c in concept_list for c in q_concepts):
                result.append(q)
                seen.add(qid)
        return result

    used_ids: set[str] = set(recent_ids)
    selected: list[dict] = []
    target_concepts: list[str] = []

    # ---------- 弱點題 (目標 10 題) ----------
    weakness_pool = questions_for_concepts(top_weak, used_ids)
    weakness_selected: list[dict] = []
    # 每個弱點概念取 2 題
    per_concept_count: dict[str, int] = defaultdict(int)
    for q in weakness_pool:
        matching = [c for c in q.get("concepts", []) if c in top_weak]
        if not matching:
            continue
        concept = matching[0]
        if per_concept_count[concept] < 2:
            weakness_selected.append(q)
            used_ids.add(q["id"])
            per_concept_count[concept] += 1
            if concept not in target_concepts:
                target_concepts.append(concept)
        if len(weakness_selected) >= 10:
            break

    selected.extend(weakness_selected)

    # ---------- 複習題 (目標 5 題) ----------
    review_pool = questions_for_concepts(review_concepts, used_ids)
    review_selected = review_pool[:5]
    for q in review_selected:
        used_ids.add(q["id"])
        for c in q.get("concepts", []):
            if c in review_concepts and c not in target_concepts:
                target_concepts.append(c)
    selected.extend(review_selected)

    # ---------- 新概念題 (目標 5 題) ----------
    new_pool = questions_for_concepts(new_concepts, used_ids)
    new_selected = new_pool[:5]
    for q in new_selected:
        used_ids.add(q["id"])
        for c in q.get("concepts", []):
            if c in new_concepts and c not in target_concepts:
                target_concepts.append(c)
    selected.extend(new_selected)

    # ---------- 不足時從剩餘題目補足 ----------
    if len(selected) < 20:
        remaining_pool = [q for q in all_questions if q.get("id") not in used_ids]
        needed = 20 - len(selected)
        fill = remaining_pool[:needed]
        for q in fill:
            used_ids.add(q["id"])
        selected.extend(fill)

    # 最多 20 題
    selected = selected[:20]

    # ---------- 計算實際組成 ----------
    weakness_ids = {q["id"] for q in weakness_selected}
    review_ids = {q["id"] for q in review_selected}
    actual_weakness = sum(1 for q in selected if q.get("id") in weakness_ids)
    actual_review = sum(1 for q in selected if q.get("id") in review_ids)
    actual_new = len(selected) - actual_weakness - actual_review

    return {
        "week": week_str,
        "questions": selected,
        "composition": {
            "weakness": actual_weakness,
            "review": actual_review,
            "new": actual_new,
        },
        "target_concepts": target_concepts,
    }


# ---------------------------------------------------------------------------
# 4. calculate_learning_stats
# ---------------------------------------------------------------------------

def calculate_learning_stats(
    concept_mastery: dict,
    sessions: list[dict],
    category_questions: dict,
) -> dict:
    """
    計算整體學習統計數據，供儀表板及雷達圖使用。

    Parameters
    ----------
    concept_mastery : dict
        概念精熟度資料（同 calculate_badges）。
    sessions : list[dict]
        練習記錄（同 calculate_streak）。
    category_questions : dict
        每個科目包含的題目 id 清單：
        {"幼兒發展與輔導": ["q_id_1", ...], ...}

    Returns
    -------
    dict
        詳見函式說明。
    """
    today = _today()

    # ---------- 概念統計 ----------
    total_concepts_available = sum(len(v) for v in CATEGORY_CONCEPTS.values())
    total_concepts_touched = len(concept_mastery)
    mastered_concepts = sum(
        1 for data in concept_mastery.values()
        if data.get("masteryScore", 0.0) >= 0.7
    )

    # ---------- 各科目精熟度 ----------
    category_mastery: dict[str, dict] = {}
    for cat, cat_concepts in CATEGORY_CONCEPTS.items():
        touched_in_cat = [c for c in cat_concepts if c in concept_mastery]
        mastered_in_cat = [
            c for c in touched_in_cat
            if concept_mastery[c].get("masteryScore", 0.0) >= 0.7
        ]
        if cat_concepts:
            # 整體精熟比例：已精熟概念 / 科目總概念數（含未觸及視為 0）
            cat_mastery_score = len(mastered_in_cat) / len(cat_concepts)
        else:
            cat_mastery_score = 0.0

        category_mastery[cat] = {
            "mastery": round(cat_mastery_score, 4),
            "concepts_mastered": len(mastered_in_cat),
            "concepts_total": len(cat_concepts),
        }

    # ---------- 週別正確率 ----------
    week_stats: dict[str, dict] = defaultdict(lambda: {"correct_sum": 0.0, "count": 0})
    for s in sessions:
        attempted = s.get("questionsAttempted", 0)
        if attempted <= 0:
            continue
        try:
            week = _get_iso_week(s["date"])
        except (KeyError, ValueError):
            continue
        correct_rate = s.get("correctRate", 0.0)
        week_stats[week]["correct_sum"] += correct_rate * attempted
        week_stats[week]["count"] += attempted

    sorted_weeks = sorted(week_stats.keys())
    weekly_accuracy: list[dict] = []
    for week in sorted_weeks:
        ws = week_stats[week]
        count = ws["count"]
        accuracy = ws["correct_sum"] / count if count > 0 else 0.0
        weekly_accuracy.append({
            "week": week,
            "accuracy": round(accuracy, 4),
            "count": count,
        })

    # ---------- 改善率（最近兩週正確率差）----------
    improvement_rate = 0.0
    if len(weekly_accuracy) >= 2:
        improvement_rate = round(
            weekly_accuracy[-1]["accuracy"] - weekly_accuracy[-2]["accuracy"], 4
        )

    # ---------- 雷達圖資料 ----------
    radar_labels = list(CATEGORY_CONCEPTS.keys())
    radar_values = [
        round(category_mastery.get(cat, {}).get("mastery", 0.0), 4)
        for cat in radar_labels
    ]

    # ---------- 預估應試準備度 ----------
    # 加權平均：各科目精熟度 + 近期正確率趨勢
    if radar_values:
        base_readiness = sum(radar_values) / len(radar_values)
    else:
        base_readiness = 0.0

    # 若有近期正確率，稍作修正（最新一週正確率與基礎分數加權）
    if weekly_accuracy:
        recent_accuracy = weekly_accuracy[-1]["accuracy"]
        estimated_readiness = round(base_readiness * 0.7 + recent_accuracy * 0.3, 4)
    else:
        estimated_readiness = round(base_readiness, 4)

    return {
        "total_concepts_touched": total_concepts_touched,
        "total_concepts_available": total_concepts_available,
        "mastered_concepts": mastered_concepts,
        "category_mastery": category_mastery,
        "weekly_accuracy": weekly_accuracy,
        "improvement_rate": improvement_rate,
        "radar_data": {
            "labels": radar_labels,
            "values": radar_values,
        },
        "estimated_readiness": estimated_readiness,
    }
