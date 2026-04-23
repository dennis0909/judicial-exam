"""
公職王 PDF 下載器 — 法警特考歷年試題解答
來源：https://www.public.com.tw

執行方式：
    pip install requests beautifulsoup4
    python scripts/scraper_public_pdf.py

輸出：data/pdfs/ 目錄 + data/pdf_index.json
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

BASE_URL = "https://www.public.com.tw"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.public.com.tw/exampoint/2024-judicial",
}
DELAY = 2.0
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "pdfs"
INDEX_FILE = Path(__file__).parent.parent / "data" / "pdf_index.json"

# 已知 PDF 直連（113年，Phase 1 已驗證）
KNOWN_PDFS = [
    {
        "year": 113, "subject": "行政法概要",
        "url": "https://www.public.com.tw/TestFileManage/21088/anspdf/113司法四等-行政法概要.pdf",
    },
    {
        "year": 113, "subject": "刑法概要",
        "url": "https://www.public.com.tw/TestFileManage/21090/anspdf/113司法特考四等-刑法概要.pdf",
    },
    {
        "year": 113, "subject": "刑事訴訟法概要",
        "url": "https://www.public.com.tw/TestFileManage/21071/anspdf/113司法四等-刑事訴訟法概要.pdf",
    },
    {
        "year": 113, "subject": "法院組織法",
        "url": "https://www.public.com.tw/TestFileManage/21078/anspdf/113司法特考四等-法院組織法.pdf",
    },
    {
        "year": 113, "subject": "國文",
        "url": "https://www.public.com.tw/TestFileManage/21069/anspdf/113司法特考四等-國文(作文與測驗).pdf",
    },
    {
        "year": 113, "subject": "法學知識與英文",
        "url": "https://www.public.com.tw/TestFileManage/21093/anspdf/113司法特考四等、海巡特考四等-法學知識與英文.pdf",
    },
]

# 各年度解答頁面 URL（公職王的解答彙整頁）
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

# 法警相關關鍵字
BAILIFF_KEYWORDS = ["法警", "judicial-bailiff", "四等_法警", "四等法警"]

# 相關科目關鍵字
SUBJECT_KEYWORDS = ["行政法概要", "刑法概要", "刑事訴訟法概要", "法院組織法", "法學知識", "國文"]


def is_bailiff_related(text: str) -> bool:
    return any(kw in text for kw in BAILIFF_KEYWORDS)


def extract_subject_from_name(filename: str) -> str:
    subjects = {
        "行政法概要": "行政法概要",
        "刑法概要": "刑法概要",
        "刑事訴訟法概要": "刑事訴訟法概要",
        "法院組織法": "法院組織法",
        "法學知識": "法學知識與英文",
        "國文": "國文",
    }
    for key, canonical in subjects.items():
        if key in filename:
            return canonical
    return "其他"


def find_pdfs_from_year_page(year: int, url: str, session: requests.Session) -> list[dict]:
    """從公職王年度解答頁找法警 PDF 連結"""
    pdfs = []
    try:
        resp = session.get(url, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            print(f"  {year}年頁面 HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # 找所有 PDF 連結
        pdf_links = soup.find_all("a", href=re.compile(r"\.pdf", re.I))
        for link in pdf_links:
            href = link.get("href", "")
            link_text = link.get_text(strip=True)
            full_text = f"{href} {link_text}"

            # 只要法警相關或主要科目
            if is_bailiff_related(full_text) or any(kw in full_text for kw in SUBJECT_KEYWORDS):
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                subject = extract_subject_from_name(full_text)
                pdfs.append({
                    "year": year,
                    "subject": subject,
                    "url": full_url,
                    "link_text": link_text,
                })

    except Exception as e:
        print(f"  {year}年頁面抓取失敗：{e}")

    return pdfs


def download_pdf(pdf_info: dict, session: requests.Session) -> str | None:
    """下載 PDF 並儲存，回傳本地路徑"""
    url = pdf_info["url"]
    year = pdf_info["year"]
    subject = pdf_info["subject"]

    # 安全檔名
    safe_subject = subject.replace("/", "").replace("\\", "").replace(":", "")
    filename = f"{year}_{safe_subject}.pdf"
    local_path = OUTPUT_DIR / str(year) / filename

    if local_path.exists():
        print(f"    已存在，略過：{filename}")
        return str(local_path)

    local_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        resp = session.get(url, timeout=30, stream=True)
        if resp.status_code == 200 and "pdf" in resp.headers.get("content-type", "").lower():
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            size_kb = local_path.stat().st_size // 1024
            print(f"    ✅ {filename} ({size_kb} KB)")
            return str(local_path)
        else:
            print(f"    ❌ HTTP {resp.status_code} 或非 PDF：{url}")
    except Exception as e:
        print(f"    ❌ 下載失敗：{e}")

    return None


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    print("=== 公職王 PDF 下載器 ===")
    all_pdfs = list(KNOWN_PDFS)  # 從已知 PDF 開始

    # Step 1：從各年度頁面爬 PDF 連結
    print("\nStep 1：從各年度解答頁找 PDF 連結...")
    for year, url in YEAR_PAGES.items():
        print(f"  {year}年：{url}")
        found = find_pdfs_from_year_page(year, url, session)
        if found:
            all_pdfs.extend(found)
            print(f"    找到 {len(found)} 個 PDF 連結")
        time.sleep(DELAY)

    # 去重（by url）
    seen_urls = set()
    unique_pdfs = []
    for pdf in all_pdfs:
        if pdf["url"] not in seen_urls:
            seen_urls.add(pdf["url"])
            unique_pdfs.append(pdf)

    print(f"\n共 {len(unique_pdfs)} 個不重複 PDF")

    # Step 2：下載
    print("\nStep 2：下載 PDF...")
    for i, pdf in enumerate(unique_pdfs, 1):
        print(f"  [{i}/{len(unique_pdfs)}] {pdf['year']}年 {pdf['subject']}")
        local_path = download_pdf(pdf, session)
        pdf["local_path"] = local_path
        time.sleep(DELAY)

    # 儲存索引
    index = {
        "crawled_at": __import__("datetime").datetime.now().isoformat(),
        "total": len(unique_pdfs),
        "downloaded": sum(1 for p in unique_pdfs if p.get("local_path")),
        "pdfs": unique_pdfs,
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n=== 完成 ===")
    print(f"已下載：{index['downloaded']}/{index['total']} 份")
    print(f"索引儲存至：{INDEX_FILE}")
    print(f"PDF 目錄：{OUTPUT_DIR}")


if __name__ == "__main__":
    run()
