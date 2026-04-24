"""
Merge lawbank questions with extracted PDF answers into questions.json.

Usage:
    python scripts/build_questions.py

Inputs:
    data/lawbank_questions.json
    data/pdf_answers.json

Output:
    questions.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "lawbank_questions.json"
PDF_ANS = ROOT / "data" / "pdf_answers.json"
DST = ROOT / "questions.json"


def run() -> None:
    with open(SRC, encoding="utf-8") as file_obj:
        raw = json.load(file_obj)

    questions = raw["questions"]

    pdf_answers = {}
    if PDF_ANS.exists():
        with open(PDF_ANS, encoding="utf-8") as file_obj:
            pdf_answers = json.load(file_obj)
        print(f"載入 PDF 答案：{len(pdf_answers)} 份")
    else:
        print("未找到 pdf_answers.json，跳過答案合併")

    merged_count = 0
    for question in questions:
        if question["type"] != "mcq" or question.get("answer"):
            continue

        roc_year = question.get("roc_year")
        subject = question.get("subject")
        question_number = question.get("question_number")
        if not all([roc_year, subject, question_number]):
            continue

        key = f"{roc_year}_{subject}"
        answers_list = pdf_answers.get(key, {}).get("answers", [])
        index = question_number - 1
        if 0 <= index < len(answers_list) and answers_list[index] != "?":
            question["answer"] = answers_list[index]
            merged_count += 1

    print(f"從 PDF 合併了 {merged_count} 題答案")

    seen_ids: dict[str, int] = {}
    for question in questions:
        base_id = question["id"]
        if base_id in seen_ids:
            seen_ids[base_id] += 1
            question["id"] = f"{base_id}_v{seen_ids[base_id]}"
        else:
            seen_ids[base_id] = 1

    question_subjects = sorted({question["subject"] for question in questions})
    pdf_subjects = sorted({payload["subject"] for payload in pdf_answers.values()})
    orphan_pdf_subjects = sorted(set(pdf_subjects) - set(question_subjects))
    if orphan_pdf_subjects:
        print(f"警告：以下 PDF 科目已有答案但題庫尚未收錄：{', '.join(orphan_pdf_subjects)}")

    output = {
        "version": "1.2",
        "total": len(questions),
        "subjects": question_subjects,
        "years": sorted({question["roc_year"] for question in questions if question["roc_year"]}),
        "questions": questions,
    }

    with open(DST, "w", encoding="utf-8") as file_obj:
        json.dump(output, file_obj, ensure_ascii=False, indent=2)

    total = len(questions)
    with_answers = sum(1 for question in questions if question.get("answer"))
    mcq_total = sum(1 for question in questions if question["type"] == "mcq")

    print(f"\n已產生 {DST}")
    print(f"總題數: {total}（選擇 {mcq_total} / 申論 {total - mcq_total}）")
    print(f"有答案: {with_answers} / {mcq_total} 選擇題（{with_answers / mcq_total * 100:.0f}%）")

    print("\n科目分布：")
    for subject, count in Counter(question["subject"] for question in questions).most_common():
        answered = sum(1 for question in questions if question["subject"] == subject and question.get("answer"))
        print(f"  {subject}: {count} 題（{answered} 有答案）")

    print("\n年度分布：")
    for roc_year, count in sorted(Counter(question["roc_year"] for question in questions).items()):
        answered = sum(1 for question in questions if question["roc_year"] == roc_year and question.get("answer"))
        print(f"  {roc_year} 年: {count} 題（{answered} 有答案）")


if __name__ == "__main__":
    run()
