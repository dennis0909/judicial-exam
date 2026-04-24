"""
將 data/lawbank_questions.json + data/pdf_answers.json 合併為 questions.json（App 使用格式）
執行：python scripts/build_questions.py
輸出：questions.json（根目錄）
"""
import json
import sys
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
SRC = ROOT / "data" / "lawbank_questions.json"
PDF_ANS = ROOT / "data" / "pdf_answers.json"
DST = ROOT / "questions.json"


def run():
    # ── 讀取 lawbank 題目 ──
    with open(SRC, encoding="utf-8") as f:
        raw = json.load(f)

    questions = raw["questions"]

    # ── 讀取 PDF 答案 ──
    pdf_answers = {}
    if PDF_ANS.exists():
        with open(PDF_ANS, encoding="utf-8") as f:
            pdf_answers = json.load(f)
        print(f"載入 PDF 答案：{len(pdf_answers)} 份")
    else:
        print("未找到 pdf_answers.json，跳過答案合併")

    # ── 合併答案 ──
    merged_count = 0
    for q in questions:
        if q["type"] != "mcq" or q.get("answer"):
            continue  # 非選擇題或已有答案，跳過

        roc_year = q.get("roc_year")
        subject = q.get("subject")
        q_num = q.get("question_number")
        if not all([roc_year, subject, q_num]):
            continue

        key = f"{roc_year}_{subject}"
        if key in pdf_answers:
            answers_list = pdf_answers[key].get("answers", [])
            idx = q_num - 1  # 答案列表 0-indexed
            if 0 <= idx < len(answers_list) and answers_list[idx] != "?":
                q["answer"] = answers_list[idx]
                merged_count += 1

    print(f"從 PDF 合併了 {merged_count} 題答案")

    # ── 確保 ID 唯一 ──
    seen_ids: dict[str, int] = {}
    for q in questions:
        base_id = q["id"]
        if base_id in seen_ids:
            seen_ids[base_id] += 1
            q["id"] = f"{base_id}_v{seen_ids[base_id]}"
        else:
            seen_ids[base_id] = 1

    # ── 產出 ──
    output = {
        "version": "1.1",
        "total": len(questions),
        "subjects": sorted({q["subject"] for q in questions}),
        "years": sorted({q["roc_year"] for q in questions if q["roc_year"]}),
        "questions": questions,
    }

    with open(DST, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # ── 統計報表 ──
    total = len(questions)
    with_ans = sum(1 for q in questions if q.get("answer"))
    mcq_total = sum(1 for q in questions if q["type"] == "mcq")

    print(f"\n已產生 {DST}")
    print(f"總題數: {total}（選擇 {mcq_total} / 申論 {total - mcq_total}）")
    print(f"有答案: {with_ans} / {mcq_total} 選擇題（{with_ans/mcq_total*100:.0f}%）")
    print("\n科目分布：")
    for s, n in Counter(q["subject"] for q in questions).most_common():
        ans_n = sum(1 for q in questions if q["subject"] == s and q.get("answer"))
        print(f"  {s}: {n} 題（{ans_n} 有答案）")

    print("\n年度分布：")
    for y, n in sorted(Counter(q["roc_year"] for q in questions).items()):
        ans_n = sum(1 for q in questions if q["roc_year"] == y and q.get("answer"))
        print(f"  {y} 年: {n} 題（{ans_n} 有答案）")


if __name__ == "__main__":
    run()
