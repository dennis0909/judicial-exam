# Next Session

> Updated: 2026-04-24
> Repo: `C:\Users\denni\judicial-exam`

## Goal

Build a usable judicial-exam question app by reusing the `exam-analyzer` architecture, but with a stable scraper pipeline first.

## Current Status

- [x] Phase 1: source reconnaissance finished
- [x] Phase 2: pipeline repaired for `scraper_lawbank.py -> scraper_public_pdf.py -> extract_pdf_answers.py -> build_questions.py`
- [ ] Phase 3: continue app fork / UI / deployment work

## Current Pipeline

```powershell
cd C:\Users\denni\judicial-exam

pip install requests beautifulsoup4 pikepdf pymupdf

python scripts\scraper_lawbank.py
python scripts\scraper_public_pdf.py
python scripts\extract_pdf_answers.py
python scripts\build_questions.py
```

## Current Outputs

- `data/lawbank_questions.json`
- `data/pdf_index.json`
- `data/pdf_answers.json`
- `questions.json`

## Important Constraints

- Lawbank currently covers only 4 subjects in this repo's dataset:
  - `行政法概要`
  - `刑法概要`
  - `刑事訴訟法概要`
  - `法院組織法`
- PDF answer extraction currently provides useful objective answers for:
  - `行政法概要`
  - `刑法概要`
  - `法學知識與英文`
- `法學知識與英文` answer keys exist, but question bodies are not yet in `lawbank_questions.json`
- `國文` PDF is downloaded, but the current app dataset still does not include its question bodies

## What Was Fixed This Session

- `scraper_public_pdf.py`
  - standardized canonical subject names
  - downloads PDFs into a stable `data/pdfs/*.pdf` flow
  - improved yearly discovery and URL normalization
- `scraper_lawbank.py`
  - cleaned parser structure
  - added hard validation for expected `(roc_year, subject)` vs parsed page metadata
  - kept output schema aligned with downstream scripts
- `extract_pdf_answers.py`
  - now scans PDFs recursively
  - dedupes duplicate files by stem
  - no longer silently misses PDFs stored under year subfolders
- `build_questions.py`
  - keeps merge logic simple and deterministic
  - warns when PDF answers exist for subjects not yet present in the question bank

## Next High-Value Tasks

1. Decide the source strategy for `法學知識與英文` and `國文` question bodies.
2. Wire the repaired `questions.json` into the app flow and subject filters.
3. Clean remaining mojibake docs inherited from older notes.
4. Keep `docs/maintenance.md` as the checklist for pruning stale memory/md/skill notes.
