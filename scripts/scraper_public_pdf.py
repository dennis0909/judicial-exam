"""
Download official judicial-exam answer PDFs from public.com.tw.

Usage:
    pip install requests beautifulsoup4
    python scripts/scraper_public_pdf.py

Output:
    data/pdfs/*.pdf
    data/pdf_index.json
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "https://www.public.com.tw"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.public.com.tw/exampoint/2024-judicial",
}
DELAY = 2.0
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "data" / "pdfs"
INDEX_FILE = ROOT / "data" / "pdf_index.json"

KNOWN_PDFS = [
    {
        "year": 113,
        "subject": "行政法概要",
        "url": "https://www.public.com.tw/TestFileManage/21088/anspdf/113司法四等-行政法概要.pdf",
    },
    {
        "year": 113,
        "subject": "刑法概要",
        "url": "https://www.public.com.tw/TestFileManage/21090/anspdf/113司法特考四等-刑法概要.pdf",
    },
    {
        "year": 113,
        "subject": "刑事訴訟法概要",
        "url": "https://www.public.com.tw/TestFileManage/21071/anspdf/113司法四等-刑事訴訟法概要.pdf",
    },
    {
        "year": 113,
        "subject": "法院組織法",
        "url": "https://www.public.com.tw/TestFileManage/21078/anspdf/113司法特考四等-法院組織法.pdf",
    },
    {
        "year": 113,
        "subject": "國文",
        "url": "https://www.public.com.tw/TestFileManage/21069/anspdf/113司法特考四等-國文(作文與測驗).pdf",
    },
    {
        "year": 113,
        "subject": "法學知識與英文",
        "url": "https://www.public.com.tw/TestFileManage/21093/anspdf/113司法特考四等、海巡特考四等-法學知識與英文.pdf",
    },
]

YEAR_PAGES = {
    114: "https://www.public.com.tw/exampoint/2025-judicial",
    113: "https://www.public.com.tw/exampoint/2024-judicial",
    112: "https://www.public.com.tw/exampoint/2023-judicial",
    111: "https://www.public.com.tw/exampoint/2022-judicial",
    110: "https://www.public.com.tw/exampoint/2021-judicial",
    109: "https://www.public.com.tw/exampoint/2020-judicial",
    108: "https://www.public.com.tw/exampoint/2019-judicial",
    107: "https://www.public.com.tw/exampoint/2018-judicial",
}

SUBJECT_ALIASES = {
    "行政法概要": "行政法概要",
    "行政法": "行政法概要",
    "刑法概要": "刑法概要",
    "刑法": "刑法概要",
    "刑事訴訟法概要": "刑事訴訟法概要",
    "刑事訴訟法": "刑事訴訟法概要",
    "刑訴": "刑事訴訟法概要",
    "法院組織法": "法院組織法",
    "法組": "法院組織法",
    "法學知識與英文": "法學知識與英文",
    "法學知識": "法學知識與英文",
    "國文": "國文",
}

BAILIFF_KEYWORDS = (
    "法警",
    "司法四等",
    "司法特考四等",
    "judicial",
)


def normalize_subject(text: str) -> str | None:
    normalized = unquote(text)
    for alias, canonical in SUBJECT_ALIASES.items():
        if alias in normalized:
            return canonical
    return None


def is_bailiff_related(text: str) -> bool:
    haystack = unquote(text).lower()
    return any(keyword.lower() in haystack for keyword in BAILIFF_KEYWORDS)


def build_filename(year: int, subject: str) -> str:
    safe_subject = re.sub(r'[\\/:*?"<>|]', "", subject).strip()
    return f"{year}_{safe_subject}.pdf"


def find_pdfs_from_year_page(year: int, url: str, session: requests.Session) -> list[dict]:
    """Discover answer-PDF links from a yearly public.com.tw exam page."""
    pdfs: list[dict] = []
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    for link in soup.find_all("a", href=re.compile(r"\.pdf(?:$|\?)", re.I)):
        href = link.get("href", "").strip()
        if not href:
            continue

        link_text = link.get_text(" ", strip=True)
        full_text = f"{unquote(href)} {link_text}"
        subject = normalize_subject(full_text)
        if not subject:
            continue
        if not is_bailiff_related(full_text):
            continue

        pdfs.append(
            {
                "year": year,
                "subject": subject,
                "url": urljoin(BASE_URL, href),
                "link_text": link_text,
                "discovered_from": url,
            }
        )

    return pdfs


def download_pdf(pdf_info: dict, session: requests.Session) -> str | None:
    """Download a single PDF into data/pdfs/ and return the local path."""
    url = pdf_info["url"]
    year = pdf_info["year"]
    subject = pdf_info["subject"]

    filename = build_filename(year, subject)
    local_path = OUTPUT_DIR / filename

    if local_path.exists():
        print(f"    already exists: {filename}")
        return str(local_path)

    resp = session.get(url, timeout=30, stream=True)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "").lower()
    if "pdf" not in content_type and not url.lower().endswith(".pdf"):
        print(f"    skipped non-pdf response: {url} ({content_type or 'unknown'})")
        return None

    with open(local_path, "wb") as file_obj:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                file_obj.write(chunk)

    size_kb = local_path.stat().st_size // 1024
    print(f"    downloaded: {filename} ({size_kb} KB)")
    return str(local_path)


def dedupe_pdfs(pdfs: list[dict]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for pdf in pdfs:
        by_url.setdefault(pdf["url"], pdf)
    return list(by_url.values())


def run() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)

    print("=== Download official answer PDFs ===")
    all_pdfs = list(KNOWN_PDFS)

    print("\nStep 1: discover yearly PDF links")
    for year, url in YEAR_PAGES.items():
        print(f"  {year}: {url}")
        try:
            discovered = find_pdfs_from_year_page(year, url, session)
            print(f"    discovered {len(discovered)} candidate PDFs")
            all_pdfs.extend(discovered)
        except Exception as exc:
            print(f"    failed: {exc}")
        time.sleep(DELAY)

    unique_pdfs = dedupe_pdfs(all_pdfs)
    print(f"\nTotal unique PDFs: {len(unique_pdfs)}")

    print("\nStep 2: download PDFs")
    for index, pdf in enumerate(unique_pdfs, 1):
        print(f"  [{index}/{len(unique_pdfs)}] {pdf['year']}年 {pdf['subject']}")
        try:
            pdf["local_path"] = download_pdf(pdf, session)
        except Exception as exc:
            print(f"    failed: {exc}")
            pdf["local_path"] = None
        time.sleep(DELAY)

    downloaded = sum(1 for pdf in unique_pdfs if pdf.get("local_path"))
    payload = {
        "crawled_at": datetime.now().isoformat(),
        "total": len(unique_pdfs),
        "downloaded": downloaded,
        "pdfs": unique_pdfs,
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)

    print("\n=== Done ===")
    print(f"Downloaded: {downloaded}/{len(unique_pdfs)}")
    print(f"Index: {INDEX_FILE}")
    print(f"PDF dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    run()
