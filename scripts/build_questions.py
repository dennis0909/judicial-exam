"""
將 data/lawbank_questions.json 轉換為 questions.json（App 使用格式）
執行：python scripts/build_questions.py
輸出：questions.json（根目錄）
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(__file__).parent.parent / "data" / "lawbank_questions.json"
DST = Path(__file__).parent.parent / "questions.json"


def run():
    with open(SRC, encoding="utf-8") as f:
        raw = json.load(f)

    questions = raw["questions"]

    # 確保 ID 唯一
    seen_ids: dict[str, int] = {}
    for q in questions:
        base_id = q["id"]
        if base_id in seen_ids:
            seen_ids[base_id] += 1
            q["id"] = f"{base_id}_v{seen_ids[base_id]}"
        else:
            seen_ids[base_id] = 1

    output = {
        "version": "1.0",
        "total": len(questions),
        "subjects": list({q["subject"] for q in questions}),
        "years": sorted({q["roc_year"] for q in questions if q["roc_year"]}),
        "questions": questions,
    }

    with open(DST, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"已產生 {DST}")
    print(f"總題數: {len(questions)}")
    from collections import Counter
    for s, n in Counter(q["subject"] for q in questions).most_common():
        print(f"  {s}: {n}")


if __name__ == "__main__":
    run()
