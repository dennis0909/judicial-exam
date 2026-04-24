"""
Merge all question sources into questions.json.

Sources (in priority order):
  1. data/lawbank_questions.json  — scraped from lawbank.com.tw
  2. data/pdf_answers.json        — answer keys from public.com.tw PDFs
  3. data/extra_questions.json    — PDF-extracted or AI-supplemented questions
                                    (法學知識與英文, 國文, etc. not on lawbank)

Usage:
    python scripts/build_questions.py

Output:
    questions.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "lawbank_questions.json"
PDF_ANS = ROOT / "data" / "pdf_answers.json"
EXTRA = ROOT / "data" / "extra_questions.json"
DST = ROOT / "questions.json"


def _ensure_id(q: dict) -> dict:
    """Guarantee every question has a stable id."""
    if not q.get("id"):
        raw = f"{q.get('roc_year','')}-{q.get('subject','')}-{q.get('question_number','')}"
        q["id"] = "q_" + hashlib.md5(raw.encode()).hexdigest()[:10]
    return q


def run() -> None:
    # ── 1. Load lawbank questions ──────────────────────────────────────────
    with open(SRC, encoding="utf-8") as f:
        raw = json.load(f)
    lawbank_qs: list[dict] = raw["questions"]
    print(f"lawbank 題數：{len(lawbank_qs)}")

    # ── 2. Merge PDF answer keys ───────────────────────────────────────────
    pdf_answers: dict = {}
    if PDF_ANS.exists():
        with open(PDF_ANS, encoding="utf-8") as f:
            pdf_answers = json.load(f)
        print(f"PDF 答案份數：{len(pdf_answers)}")
    else:
        print("未找到 pdf_answers.json，跳過答案合併")

    merged_count = 0
    for q in lawbank_qs:
        if q["type"] != "mcq" or q.get("answer"):
            continue
        key = f"{q.get('roc_year')}_{q.get('subject')}"
        answers_list = pdf_answers.get(key, {}).get("answers", [])
        idx = (q.get("question_number") or 0) - 1
        if 0 <= idx < len(answers_list) and answers_list[idx] != "?":
            q["answer"] = answers_list[idx]
            merged_count += 1
    print(f"從 PDF 合併了 {merged_count} 題答案")

    # ── 3. Load extra questions (PDF-extracted / AI-supplemented) ─────────
    extra_qs: list[dict] = []
    if EXTRA.exists():
        with open(EXTRA, encoding="utf-8") as f:
            extra_qs = json.load(f)["questions"]
        print(f"extra 題數：{len(extra_qs)}")
    else:
        print("未找到 extra_questions.json，跳過額外題目")

    # ── 4. Merge: lawbank takes precedence for its subjects ────────────────
    # Build set of (roc_year, subject) pairs covered by lawbank
    lawbank_coverage: set[tuple] = {(q["roc_year"], q["subject"]) for q in lawbank_qs}

    # Keep extra questions only if lawbank doesn't already cover that (year, subject)
    extra_kept = [
        q for q in extra_qs
        if (q.get("roc_year"), q.get("subject")) not in lawbank_coverage
    ]
    extra_dropped = len(extra_qs) - len(extra_kept)
    if extra_dropped:
        print(f"extra 中 {extra_dropped} 題與 lawbank 重疊，已略過（以 lawbank 版本為準）")

    all_questions = lawbank_qs + extra_kept
    print(f"合計題數（合併前去重）：{len(all_questions)}")

    # ── 5. Deduplicate by id ───────────────────────────────────────────────
    seen_ids: dict[str, int] = {}
    for q in all_questions:
        _ensure_id(q)
        base_id = q["id"]
        if base_id in seen_ids:
            seen_ids[base_id] += 1
            q["id"] = f"{base_id}_v{seen_ids[base_id]}"
        else:
            seen_ids[base_id] = 1

    # ── 6. Warn about orphan PDF subjects ─────────────────────────────────
    question_subjects = sorted({q["subject"] for q in all_questions})
    pdf_subjects = sorted({v["subject"] for v in pdf_answers.values()})
    orphan = sorted(set(pdf_subjects) - set(question_subjects))
    if orphan:
        print(f"警告：PDF 答案有科目但題庫無題目：{', '.join(orphan)}")

    # ── 6b. Apply hardcoded answer patches ────────────────────────────────
    HARDCODED_ANSWERS: dict[tuple, str] = {}
    ANSWERS_114_ADMIN    = "BDADCABCACADBDABBCCADBBCDDCCCCAABCDAADBBDCDBBBCCCD"
    ANSWERS_114_CRIMINAL = "CDDDDCBBBBABBBBAAAAACBBDABBBAAAABDBAAACDDCCABDBBBC"
    for i, letter in enumerate(ANSWERS_114_ADMIN):
        HARDCODED_ANSWERS[(114, "行政法概要", i + 1)] = letter
    for i, letter in enumerate(ANSWERS_114_CRIMINAL):
        HARDCODED_ANSWERS[(114, "刑法概要", i + 1)] = letter

    patched = 0
    for q in all_questions:
        if q["type"] == "mcq" and not q.get("answer"):
            key = (q.get("roc_year"), q.get("subject"), q.get("question_number"))
            if key in HARDCODED_ANSWERS:
                q["answer"] = HARDCODED_ANSWERS[key]
                patched += 1
    if patched:
        print(f"hardcoded 補答案：{patched} 題")

    # ── 7. Write output ───────────────────────────────────────────────────
    output = {
        "version": "1.3",
        "total": len(all_questions),
        "subjects": question_subjects,
        "years": sorted({q["roc_year"] for q in all_questions if q.get("roc_year")}),
        "questions": all_questions,
    }
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # ── 8. Summary ────────────────────────────────────────────────────────
    total = len(all_questions)
    mcq_total = sum(1 for q in all_questions if q["type"] == "mcq")
    with_ans = sum(1 for q in all_questions if q.get("answer"))

    print(f"\n已產生 {DST}")
    print(f"總題數: {total}（選擇 {mcq_total} / 申論 {total - mcq_total}）")
    print(f"有答案: {with_ans} / {mcq_total} 選擇題（{with_ans / mcq_total * 100:.0f}%）" if mcq_total else "")

    print("\n科目分布：")
    for subj, cnt in Counter(q["subject"] for q in all_questions).most_common():
        ans = sum(1 for q in all_questions if q["subject"] == subj and q.get("answer"))
        src = "extra" if any(q["subject"] == subj for q in extra_kept) else "lawbank"
        print(f"  {subj}: {cnt} 題（{ans} 有答案）[{src}]")

    print("\n年度分布：")
    for yr, cnt in sorted(Counter(q["roc_year"] for q in all_questions).items()):
        ans = sum(1 for q in all_questions if q["roc_year"] == yr and q.get("answer"))
        print(f"  {yr} 年: {cnt} 題（{ans} 有答案）")


if __name__ == "__main__":
    run()
