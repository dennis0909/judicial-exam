"""
Extract answer keys from downloaded official PDFs.

Usage:
    python scripts/extract_pdf_answers.py

Output:
    data/pdf_answers.json
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zlib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

try:
    import pikepdf
except ImportError:
    print("Missing dependency: pip install pikepdf")
    sys.exit(1)

try:
    import fitz  # PyMuPDF

    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

PRIVATE_CHAR_MAP: dict[str, str] = {
    "\ue2b7": "A",
    "\ue2b8": "B",
    "\ue2b9": "C",
    "\ue2ba": "D",
}

ANSWER_HASHES: dict[str, str] = {
    # 113_行政法概要
    "b85cfa95a61d17c653a3966028d69e71": "D",
    "3609ba45be8dd729c06e1a4ac93cbd8a": "A",
    "3982d818f7ca9bd991956019b7378780": "B",
    "45bd951c9c309bffb0b5a16f5ca4722d": "C",
    # 113_刑法概要
    "fdfa7b27fa1c4d76b28c0c3578810be5": "A",
    "7f74a5f8f6f7726dddfd45e812070351": "C",
    "2be2f67f478357ee431d56451c485b0e": "D",
    "422da79441cf733527a81121ee395449": "B",
}

ESSAY_SUBJECTS = {"法院組織法", "刑事訴訟法概要"}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PDF_DIR = DATA_DIR / "pdfs"
OUTPUT_FILE = DATA_DIR / "pdf_answers.json"


def get_smask_hash(pdf: pikepdf.Pdf, xobj: pikepdf.Object) -> str | None:
    smask = xobj.get("/SMask")
    if not smask:
        return None
    smask_obj = pdf.get_object(smask.objgen) if hasattr(smask, "objgen") else smask
    raw = bytes(smask_obj.read_raw_bytes())
    return hashlib.md5(raw).hexdigest()


def read_stream_bytes(stream_obj) -> bytes:
    try:
        raw = bytes(stream_obj.read_raw_bytes())
        try:
            return zlib.decompress(raw)
        except Exception:
            return raw
    except Exception:
        return b""


def extract_answers_from_pdf(pdf_path: Path) -> list[str]:
    """Extract answer letters by detecting tiny answer-marker image XObjects."""
    pdf = pikepdf.open(pdf_path)
    answers: list[tuple[int, float, str]] = []

    for page_idx, page in enumerate(pdf.pages):
        resources = page.get("/Resources")
        if not resources:
            continue
        xobjects = resources.get("/XObject", {})
        contents_obj = page.get("/Contents")
        if contents_obj is None:
            continue

        stream_text = ""
        try:
            raw = bytes(contents_obj.read_raw_bytes())
            try:
                stream_text = zlib.decompress(raw).decode("latin-1", errors="replace")
            except Exception:
                stream_text = raw.decode("latin-1", errors="replace")
        except Exception:
            try:
                for content_stream in contents_obj:
                    if hasattr(content_stream, "read_raw_bytes"):
                        stream_text += read_stream_bytes(content_stream).decode("latin-1", errors="replace")
            except Exception:
                pass

        answer_imgs: list[tuple[float, str]] = []
        for match in re.finditer(r"([\d.]+) 0 0 ([\d.]+) ([\d.]+) ([\d.]+) cm[\r\n]+/(\w+) Do", stream_text):
            width = float(match.group(1))
            x = float(match.group(3))
            y = float(match.group(4))
            img_name = match.group(5)
            if width < 30 and 40 <= x <= 55:
                answer_imgs.append((y, img_name))

        for y, img_name in sorted(answer_imgs, key=lambda item: -item[0]):
            xobj_ref = xobjects.get("/" + img_name)
            if not xobj_ref:
                continue
            try:
                xobj = pdf.get_object(xobj_ref.objgen) if hasattr(xobj_ref, "objgen") else xobj_ref
                hash_value = get_smask_hash(pdf, xobj)
                letter = ANSWER_HASHES.get(hash_value, "?") if hash_value else "?"
                answers.append((page_idx, y, letter))
            except Exception:
                continue

    answers.sort(key=lambda item: (item[0], -item[1]))
    return [letter for _, _, letter in answers]


def extract_answers_private_char(pdf_path: Path) -> list[str]:
    """Fallback for PDFs that encode answer letters as private Unicode glyphs."""
    if not HAS_FITZ:
        return []

    pdf = fitz.open(str(pdf_path))
    answers: list[str] = []
    for page in pdf:
        page_answers: list[tuple[float, str]] = []
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    x = span["bbox"][0]
                    y = span["bbox"][1]
                    if x < 50 and len(text) == 1 and text in PRIVATE_CHAR_MAP:
                        page_answers.append((y, PRIVATE_CHAR_MAP[text]))
        page_answers.sort(key=lambda item: item[0])
        answers.extend(letter for _, letter in page_answers)

    return answers


def collect_pdf_files() -> list[Path]:
    """Recursively collect PDFs and dedupe by filename stem."""
    selected: dict[str, Path] = {}
    for pdf_path in sorted(PDF_DIR.rglob("*.pdf")):
        key = pdf_path.stem
        current = selected.get(key)
        if current is None:
            selected[key] = pdf_path
            continue

        # Prefer the shallower path to avoid processing both root and year-subdir duplicates.
        if len(pdf_path.relative_to(PDF_DIR).parts) < len(current.relative_to(PDF_DIR).parts):
            selected[key] = pdf_path

    return [selected[key] for key in sorted(selected)]


def run() -> None:
    print("=== Extract PDF answer keys ===")
    pdfs = collect_pdf_files()
    print(f"Found {len(pdfs)} unique PDFs")

    results = {}

    for pdf_path in pdfs:
        stem = pdf_path.stem
        parts = stem.split("_", 1)
        if len(parts) != 2:
            continue

        try:
            roc_year = int(parts[0])
        except ValueError:
            continue

        subject = parts[1]
        print(f"\nProcessing: {pdf_path.relative_to(PDF_DIR)}")

        if subject in ESSAY_SUBJECTS:
            print("  skipped essay-only subject")
            continue

        if subject == "法學知識與英文":
            answers = extract_answers_private_char(pdf_path)
        else:
            answers = extract_answers_from_pdf(pdf_path)

        if not answers:
            print("  no answer key extracted")
            continue

        print(f"  extracted {len(answers)} answers")
        results[f"{roc_year}_{subject}"] = {
            "roc_year": roc_year,
            "subject": subject,
            "answers": answers,
            "pdf_path": str(pdf_path),
        }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(results, file_obj, ensure_ascii=False, indent=2)

    total_answers = sum(len(value["answers"]) for value in results.values())
    print(f"\nOutput: {OUTPUT_FILE}")
    print(f"Subjects with answers: {len(results)}")
    print(f"Total extracted answers: {total_answers}")


if __name__ == "__main__":
    run()
