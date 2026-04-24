"""
Scrape judicial-exam questions from lawbank.com.tw.

Usage:
    pip install requests beautifulsoup4
    python scripts/scraper_lawbank.py

Output:
    data/lawbank_questions.json
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "https://www.lawbank.com.tw"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.lawbank.com.tw/exam/",
}
DELAY = 1.2
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "lawbank_questions.json"

KNOWN_EIDS = {
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
    (86, "法院組織法"): 1838,
}

SUBJECT_KEYWORDS = {
    "行政法概要": ["行政法概要", "行政法"],
    "法院組織法": ["法院組織法", "法組"],
    "刑法概要": ["刑法概要", "刑法"],
    "刑事訴訟法概要": ["刑事訴訟法概要", "刑事訴訟法", "刑訴"],
    "法學知識與英文": ["法學知識與英文", "法學知識"],
    "國文": ["國文"],
}

ESSAY_SUBJECTS = {"法院組織法", "刑事訴訟法概要"}
CHINESE_NUMS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def parse_subject(title: str) -> str | None:
    for canonical, keywords in SUBJECT_KEYWORDS.items():
        if any(keyword in title for keyword in keywords):
            return canonical
    return None


def parse_roc_year(text: str) -> int | None:
    match = re.search(r"(\d{2,3})\s*年", text)
    return int(match.group(1)) if match else None


def parse_meta(soup: BeautifulSoup) -> dict[str, str]:
    meta: dict[str, str] = {}
    meta_table = soup.find("table", class_="resultsArticle-Table")
    if not meta_table:
        return meta

    for row in meta_table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        label = cells[0]
        value = cells[-1]
        if any(token in label for token in ("類科", "考試別", "等別")):
            meta["category"] = value
        elif "科目" in label:
            meta["subject_raw"] = value
        elif any(token in label for token in ("年度", "年別")):
            meta["roc_year_raw"] = value
    return meta


def extract_text_lines(td) -> list[str]:
    raw_text = td.get_text("\n", strip=True)
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def parse_mcq_lines(lines: list[str]) -> tuple[int, str, dict[str, str]] | None:
    first = lines[0]
    q_match = re.match(r"^(\d+)\s*[.、]?\s*(.+)$", first)
    if not q_match:
        return None

    question_number = int(q_match.group(1))
    stem_parts = [q_match.group(2).strip()]
    options: dict[str, str] = {}

    for line in lines[1:]:
        opt_match = re.match(r"^[（(]?\s*([ABCDabcd])\s*[）).、]?\s*(.+)$", line)
        if opt_match:
            options[opt_match.group(1).upper()] = opt_match.group(2).strip()
        elif not options:
            stem_parts.append(line)

    if not options:
        return None
    return question_number, " ".join(stem_parts).strip(), options


def parse_essay_blocks(raw_text: str) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    pattern = re.compile(r"(?:^|\n)\s*([一二三四五六七八九十])\s*[、.]\s*(.+?)(?=(?:\n\s*[一二三四五六七八九十]\s*[、.])|$)", re.DOTALL)
    for match in pattern.finditer(raw_text):
        chinese_number = match.group(1)
        stem = match.group(2).strip()
        question_number = CHINESE_NUMS.get(chinese_number)
        if question_number is not None and stem:
            results.append((question_number, stem))
    return results


def parse_exam_page(
    eid: int,
    session: requests.Session,
    *,
    expected_roc_year: int,
    expected_subject: str,
) -> dict | None:
    """Fetch one EID page and return metadata plus parsed questions."""
    url = f"{BASE_URL}/exam/exam.aspx?EID={eid}"
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    meta = parse_meta(soup)
    subject_raw = meta.get("subject_raw", "")
    parsed_subject = parse_subject(subject_raw)
    parsed_roc_year = parse_roc_year(meta.get("roc_year_raw", ""))

    if parsed_subject != expected_subject or parsed_roc_year != expected_roc_year:
        print(
            "  metadata mismatch:"
            f" expected=({expected_roc_year}, {expected_subject})"
            f" parsed=({parsed_roc_year}, {parsed_subject})"
        )
        return None

    q_tables = soup.find_all("table", class_="resultsArticle2-Table")
    q_table = next((table for table in q_tables if "RelaLink" not in (table.get("class") or [])), None)
    if not q_table:
        print("  no question table found")
        return None

    questions: list[dict] = []
    for row_idx, row in enumerate(q_table.find_all("tr"), start=1):
        td = row.find("td")
        if not td:
            continue

        lines = extract_text_lines(td)
        if not lines:
            continue

        mcq = parse_mcq_lines(lines)
        if mcq:
            question_number, stem, options = mcq
            questions.append(
                {
                    "id": f"{parsed_roc_year}_{parsed_subject}_{question_number}",
                    "roc_year": parsed_roc_year,
                    "year_ad": parsed_roc_year + 1911,
                    "subject": parsed_subject,
                    "subject_raw": subject_raw,
                    "exam_category": meta.get("category", "法警"),
                    "question_number": question_number,
                    "type": "mcq",
                    "stem": stem,
                    "options": options,
                    "answer": None,
                    "explanation": None,
                    "source": "法源法律網",
                    "source_eid": str(eid),
                }
            )
            continue

        raw_text = td.get_text("\n", strip=True)
        essay_blocks = parse_essay_blocks(raw_text)
        if not essay_blocks:
            continue

        for question_number, stem in essay_blocks:
            questions.append(
                {
                    "id": f"{parsed_roc_year}_{parsed_subject}_{question_number}",
                    "roc_year": parsed_roc_year,
                    "year_ad": parsed_roc_year + 1911,
                    "subject": parsed_subject,
                    "subject_raw": subject_raw,
                    "exam_category": meta.get("category", "法警"),
                    "question_number": question_number,
                    "type": "essay",
                    "stem": stem,
                    "options": {},
                    "answer": None,
                    "explanation": None,
                    "source": "法源法律網",
                    "source_eid": str(eid),
                }
            )

    return {
        "eid": eid,
        "meta": meta,
        "questions": questions,
        "roc_year": parsed_roc_year,
        "subject": parsed_subject,
    }


def run() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)

    print("=== Scrape judicial-exam questions from Lawbank ===")
    print(f"Known EIDs: {len(KNOWN_EIDS)}")

    all_questions: list[dict] = []
    exam_results: list[dict] = []

    for (roc_year, subject), eid in KNOWN_EIDS.items():
        print(f"  [{roc_year}年 {subject}] EID={eid}")
        try:
            result = parse_exam_page(
                eid,
                session,
                expected_roc_year=roc_year,
                expected_subject=subject,
            )
        except Exception as exc:
            print(f"    failed: {exc}")
            result = None

        if result and result["questions"]:
            count = len(result["questions"])
            mcq_count = sum(1 for item in result["questions"] if item["type"] == "mcq")
            print(f"    -> {count} 題 ({mcq_count} 選擇 / {count - mcq_count} 申論)")
            all_questions.extend(result["questions"])
            exam_results.append(
                {
                    "eid": eid,
                    "roc_year": result["roc_year"],
                    "subject": result["subject"],
                    "count": count,
                }
            )
        else:
            print("    -> 0 題")

        time.sleep(DELAY)

    output = {
        "source": "法源法律網",
        "note": "答案與解析若為 null，通常表示法源頁面未提供或需額外付費內容。",
        "crawled_at": datetime.now().isoformat(),
        "total": len(all_questions),
        "exams": exam_results,
        "questions": all_questions,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(output, file_obj, ensure_ascii=False, indent=2)

    print("\n=== Done ===")
    print(f"Total questions: {len(all_questions)}")
    print(f"Answered in source: {sum(1 for item in all_questions if item.get('answer'))}")
    print("Subjects:")
    for subject, count in Counter(item["subject"] for item in all_questions).most_common():
        print(f"  {subject}: {count}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
