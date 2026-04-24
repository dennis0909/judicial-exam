import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
Q_FILE = ROOT / "questions.json"

ANSWERS_114_ADMIN = "BDADCABCACADBDABBCCADBBCDDCCCCAABCDAADBBDCDBBBCCCD"
ANSWERS_114_CRIMINAL = "CDDDDCBBBBABBBBAAAAACBBDABBBAAAABDBAAACDDCCABDBBBC"

def patch_answers():
    with open(Q_FILE, encoding="utf-8") as f:
        data = json.load(f)

    patched_count = 0
    for q in data["questions"]:
        if q["roc_year"] == 114 and q["type"] == "mcq" and not q.get("answer"):
            idx = q["question_number"] - 1
            if q["subject"] == "行政法概要":
                if 0 <= idx < len(ANSWERS_114_ADMIN):
                    q["answer"] = ANSWERS_114_ADMIN[idx]
                    patched_count += 1
            elif q["subject"] == "刑法概要":
                if 0 <= idx < len(ANSWERS_114_CRIMINAL):
                    q["answer"] = ANSWERS_114_CRIMINAL[idx]
                    patched_count += 1

    with open(Q_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"成功補上 {patched_count} 題 114 年答案！")

if __name__ == "__main__":
    patch_answers()
