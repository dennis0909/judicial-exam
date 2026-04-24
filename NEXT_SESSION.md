# Next Session

> Updated: 2026-04-24
> Repo: `C:\Users\denni\judicial-exam`

## Goal

Build a usable judicial-exam question app — pipeline stable, app running on Render.

## ⚡ 下次優先順序

1. **Render 部署** — 在 dashboard 連 repo 即可，render.yaml 已設定好
2. **111年 法學知識與英文** — 需手動找 PDF（public.com.tw 或 moex.gov.tw 無法自動抓）
3. **108-110年 法學知識與英文** — 同上，需手動找 PDF

## Current Status

- [x] Phase 1: source reconnaissance finished
- [x] Phase 2: pipeline repaired
- [x] Phase 3: App 完成（練習/瀏覽/統計/考試資訊）
- [x] GitHub push 完成
- [x] Dead code 清除
- [x] Runtime bugs 修復
- [x] 112年 行政法/刑法 答案補充完成
- [x] PDF 萃取修正（y-gap 過濾誤觸 marker）
- [x] API / 前端接答案顯示（CSS bug 修正：reveal-correct selector）
- [x] 112年 法學知識與英文 50題 萃取完成（Public.com.tw PDF）
- [ ] 111年 法學知識與英文（PDF 找不到，需手動查找）
- [ ] Render 部署（render.yaml 已加，等在 dashboard 連 repo）

## Data Pipeline

```powershell
cd C:\Users\denni\judicial-exam

# 依序執行（通常只在新 PDF/爬蟲更新後才需要重跑）
python scripts\scraper_lawbank.py         # → data/lawbank_questions.json
python scripts\scraper_public_pdf.py      # → data/pdfs/*.pdf
python scripts\extract_pdf_answers.py     # → data/pdf_answers.json
python scripts\build_questions.py         # → questions.json（合併所有來源）
```

## Current Questions.json

| 科目 | 題數 | 有答案 | 來源 |
|------|------|--------|------|
| 行政法概要 | 150 | 149 | lawbank(112-114) + PDF(112,113) + hardcoded(114) |
| 刑法概要 | 150 | 150 | lawbank(112-114) + PDF(112,113) + hardcoded(114) |
| 刑事訴訟法概要 | 28 | 0 | lawbank(108-114) 申論題 |
| 法院組織法 | 32 | 0 | lawbank(86, 108-114) 申論題 |
| 法學知識與英文 | 100 | 100 | extra_questions.json（112-113年 PDF 提取）|
| 國文 | 10 | 10 | extra_questions.json（113年 PDF 提取）|
| **合計** | **470** | **409/410 MCQ (99.8%)** | |

> 缺 1 題：113年行政法概要（PDF 有一個 marker 抓不到，原因待查）

## Data Sources 上限

| 科目 | lawbank 可爬年份 | 說明 |
|------|----------------|------|
| 行政法概要 | 112–114 | 法警在 112年才新增此科 |
| 刑法概要 | 112–114 | 同上 |
| 法院組織法 | 86, 108–114 | 已全數抓完 |
| 刑事訴訟法概要 | 108–114 | 已全數抓完 |
| 法學知識與英文 | ❌ 不在 lawbank | 需手動下載 PDF |
| 國文 | ❌ 不在 lawbank | 需手動下載 PDF |

## 待補資料

### 112年 行政法概要 + 刑法概要 答案（101題）
- 公職王 PDF URL 格式和 113年不同，無法自動猜測
- 手動在 https://www.public.com.tw/exampoint/2023-judicial 找到 PDF 後：
  1. 存成 `data/pdfs/112_行政法概要.pdf` / `data/pdfs/112_刑法概要.pdf`
  2. 跑 `python scripts/extract_pdf_answers.py`
  3. 跑 `python scripts/build_questions.py`

### 法學知識與英文 其他年份（108-112年）
- 同樣需要手動從 public.com.tw 或考選部下載 PDF
- PDF 下載後放入 `data/pdfs/`，格式：`{年份}_法學知識與英文.pdf`
- 跑完整 pipeline 即可自動提取題目和答案

## Pipeline 說明（data sources）

- `data/lawbank_questions.json` — 法源法律網爬蟲輸出（360題）
- `data/pdf_answers.json` — 公職王 PDF 解析答案（SMask 技術）
- `data/extra_questions.json` — PDF 提取或 AI 補充（法學知識50題+國文10題）
- `questions.json` — 三個來源合併後最終輸出，不要手動編輯

## Key Files

```
main.py             FastAPI app（db.init_db 在啟動時自動執行）
auth_firebase.py    verify_id_token()（非 verify_firebase_token）
db.py               精簡版 SQLite（users/profiles/events）
utils.py            SUBJECTS、normalize_subject
static/             前端 HTML/CSS/JS
scripts/            四個 pipeline 腳本
data/extra_questions.json  ← 重要：法學知識/國文來源，不要刪
```

## Render 部署步驟

1. 在 Render dashboard 新增 Web Service
2. 連接 GitHub repo `judicial-exam`
3. 設定環境變數：`FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`
4. render.yaml 已設定 healthCheckPath: /api/stats
