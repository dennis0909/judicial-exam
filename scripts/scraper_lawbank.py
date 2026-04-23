"""
法源法律網 法警考古題爬蟲
來源：https://www.lawbank.com.tw/exam/exam.aspx?EID=XXXX

注意：
- 免費版只能看題幹+選項，答案需 VIP → 答案欄留 null
- EID 已從 Phase 1 偵查取得（10份免費）+ 已知歷年 EID 推算

執行：
    pip install requests beautifulsoup4
    python scripts/scraper_lawbank.py

輸出：data/lawbank_questions.json
"""

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "https://www.lawbank.com.tw"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.lawbank.com.tw/exam/",
}
DELAY = 1.2
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "lawbank_questions.json"

# Phase 1 確認可存取的 EID（免費10份 + 已知歷年）
KNOWN_EIDS = {
    # (roc_year, subject_canonical): eid  — 從 Phase 1 偵查 + 相關考題連結發現
    (114, "行政法概要"): 8007,
    (114, "法院組織法"): 8008,
    (114, "刑法概要"): 8009,
    (114, "刑事訴訟法概要"): 8010,
    (113, "行政法概要"): 7634,
    (113, "法院組織法"): 7635,
    (113, "刑法概要"): 7636,
    (113, "刑事訴訟法概要"): 7637,
    (112, "行政法概要"): 7378,
    (112, "法院組織法"): 7386,
    (112, "刑法概要"): 7388,
    (112, "刑事訴訟法概要"): 7397,
    (111, "法院組織法"): 6959,
    (111, "刑事訴訟法概要"): 6961,
    (110, "法院組織法"): 6813,
    (110, "刑事訴訟法概要"): 6817,
    (109, "法院組織法"): 6624,
    (109, "刑事訴訟法概要"): 6626,
    (108, "法院組織法"): 6380,
    (108, "刑事訴訟法概要"): 6382,
    (86,  "法院組織法"): 1838,
}

SUBJECT_KEYWORDS = {
    "行政法概要": ["行政法概要", "行政法"],
    "法院組織法": ["法院組織法", "法組"],
    "刑法概要": ["刑法概要", "刑法"],
    "刑事訴訟法概要": ["刑事訴訟法概要", "刑訴"],
    "法學知識與英文": ["法學知識", "法學知識與英文"],
    "國文": ["國文"],
}


def parse_subject(title: str) -> str:
    for canonical, keywords in SUBJECT_KEYWORDS.items():
        if any(k in title for k in keywords):
            return canonical
    return "其他"


def parse_roc_year(title: str) -> int | None:
    m = re.search(r"(\d{2,3})\s*年", title)
    if m:
        y = int(m.group(1))
        return y  # 民國年
    return None


def parse_exam_page(eid: int, session: requests.Session) -> dict | None:
    """抓取並解析單一試卷頁，回傳 {meta, questions}"""
    url = f"{BASE_URL}/exam/exam.aspx?EID={eid}"
    try:
        resp = session.get(url, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # ── metadata（第一個 table）──
        meta_table = soup.find("table", class_="resultsArticle-Table")
        meta = {}
        if meta_table:
            for row in meta_table.find_all("tr"):
                text = row.get_text(separator=":", strip=True)
                if "類　　科" in text or "類科" in text:
                    meta["category"] = text.split(":")[-1].strip()
                elif "科　　目" in text or "科目" in text:
                    meta["subject_raw"] = text.split(":")[-1].strip()
                elif "年　　度" in text or "年度" in text:
                    meta["roc_year_raw"] = text.split(":")[-1].strip()

        # ── 題目（第二個 table，class=resultsArticle2-Table，非 RelaLink）──
        q_tables = soup.find_all("table", class_="resultsArticle2-Table")
        q_table = None
        for t in q_tables:
            if "RelaLink" not in (t.get("class") or []):
                q_table = t
                break

        if not q_table:
            return None

        # 從 metadata 取科目 / 年份
        subject_raw = meta.get("subject_raw", "")
        subject = parse_subject(subject_raw)
        roc_year_str = meta.get("roc_year_raw", "")
        try:
            roc_year = int(roc_year_str.strip())
        except Exception:
            roc_year = None

        CHINESE_NUMS = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}

        questions = []
        for row_idx, row in enumerate(q_table.find_all("tr")):
            td = row.find("td")
            if not td:
                continue

            # 取出 <br/> 分隔的文字行
            lines = []
            for content in td.children:
                if hasattr(content, "name") and content.name == "br":
                    lines.append(None)  # 分隔符
                else:
                    t = str(content).strip()
                    if t:
                        lines.append(t)
            # 展開並清理
            flat = []
            for l in lines:
                if l is None:
                    pass
                else:
                    flat.extend(l.split("\n"))
            lines = [l.strip() for l in flat if l.strip()]

            if not lines:
                continue

            first = lines[0]

            # ── 選擇題（阿拉伯數字題號）──
            q_match = re.match(r"^(\d+)\s+(.+)", first)
            if q_match:
                q_num = int(q_match.group(1))
                stem = q_match.group(2).strip()
                options = {}
                for line in lines[1:]:
                    opt = re.match(r"^[（(]([ABCDabcd])[）)]\s*(.+)", line)
                    if opt:
                        options[opt.group(1).upper()] = opt.group(2).strip()
                    elif not re.match(r"^[（(]", line):
                        stem += " " + line
                q_type = "mcq"
                q_id = f"{roc_year}_{subject}_{q_num}" if roc_year and subject else f"eid{eid}_{q_num}"
                questions.append({
                    "id": q_id, "roc_year": roc_year,
                    "year_ad": roc_year + 1911 if roc_year and roc_year < 200 else None,
                    "subject": subject, "subject_raw": subject_raw,
                    "exam_category": meta.get("category", "法警"),
                    "question_number": q_num, "type": q_type,
                    "stem": stem, "options": options,
                    "answer": None, "explanation": None,
                    "source": "法源法律網", "source_eid": str(eid),
                })
                continue

            # ── 申論題（中文數字題號：一、二、三、四）──
            # 整個 td 可能包含多題，用中文題號切割
            full_text = td.get_text(separator="\n", strip=True)
            # 切割點：行首出現 一、二、三... 或數字
            parts = re.split(r"(?=^[一二三四五六七八九十]+[、．])", full_text, flags=re.MULTILINE)
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                cn_match = re.match(r"^([一二三四五六七八九十]+)[、．]\s*(.+)", part, re.DOTALL)
                if cn_match:
                    cn_num = cn_match.group(1)
                    q_num = CHINESE_NUMS.get(cn_num, row_idx + 1)
                    stem = cn_match.group(2).strip()
                    q_id = f"{roc_year}_{subject}_{q_num}" if roc_year and subject else f"eid{eid}_e{q_num}"
                    questions.append({
                        "id": q_id, "roc_year": roc_year,
                        "year_ad": roc_year + 1911 if roc_year and roc_year < 200 else None,
                        "subject": subject, "subject_raw": subject_raw,
                        "exam_category": meta.get("category", "法警"),
                        "question_number": q_num, "type": "essay",
                        "stem": stem, "options": {},
                        "answer": None, "explanation": None,
                        "source": "法源法律網", "source_eid": str(eid),
                    })

        return {"eid": eid, "meta": meta, "questions": questions}

    except Exception as e:
        print(f"  EID={eid} 錯誤：{e}")
        return None


def run():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    print("=== 法源法律網 法警考古題爬蟲 ===")
    print(f"目標 EID 數：{len(KNOWN_EIDS)}")

    all_questions = []
    exam_results = []

    for (roc_year, subject), eid in KNOWN_EIDS.items():
        print(f"  [{roc_year}年 {subject}] EID={eid}")
        result = parse_exam_page(eid, session)
        if result and result["questions"]:
            n = len(result["questions"])
            mcq = sum(1 for q in result["questions"] if q["type"] == "mcq")
            print(f"    -> {n} 題（{mcq} 選擇 / {n-mcq} 申論）")
            all_questions.extend(result["questions"])
            exam_results.append({"eid": eid, "roc_year": roc_year, "subject": subject, "count": n})
        else:
            print(f"    -> 0 題（空白或解析失敗）")
        time.sleep(DELAY)

    print(f"\n=== 完成 ===")
    print(f"總題數：{len(all_questions)}")
    print(f"有答案：{sum(1 for q in all_questions if q['answer'])}")

    from collections import Counter
    subj_count = Counter(q["subject"] for q in all_questions)
    print("科目分布：")
    for s, n in subj_count.most_common():
        print(f"  {s}: {n} 題")

    output = {
        "source": "法源法律網",
        "note": "答案欄 null = 需 VIP，待補",
        "crawled_at": __import__("datetime").datetime.now().isoformat(),
        "total": len(all_questions),
        "exams": exam_results,
        "questions": all_questions,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n已儲存：{OUTPUT_FILE}")


if __name__ == "__main__":
    run()
