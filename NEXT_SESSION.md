# 下個 Session 繼續這裡

> 建立：2026-04-23
> 專案路徑：C:\Users\denni\judicial-exam\

## 目標

建立「司法特考四等法警考古題分析系統」，功能比照 `C:\Users\denni\exam-analyzer\`

## 目前進度

- [x] Phase 1：資料源偵查完成（見 docs/phase1-recon.md）
- [ ] Phase 2：執行爬蟲，取得題目資料
- [ ] Phase 3：Fork exam-analyzer，建立 judicial-exam App

---

## Phase 2：立即執行（不需分析，直接跑）

```bash
cd C:\Users\denni\judicial-exam

# 安裝依賴
pip install requests beautifulsoup4

# Step 1：爬法源法律網（含解析，預計 500+ 題）
python scripts/scraper_lawbank.py
# 輸出：data/lawbank_questions.json

# Step 2：下載公職王 PDF
python scripts/scraper_public_pdf.py
# 輸出：data/pdfs/ + data/pdf_index.json
```

執行後確認：
- `data/lawbank_questions.json` 的 total 數量
- `data/pdfs/` 下有幾個 PDF
- 有多少題有 answer（非 null）

---

## Phase 3：Fork exam-analyzer → judicial-exam

參考 `C:\Users\denni\exam-analyzer\` 的結構：

### 複用（不改）
- auth_firebase.py
- db.py
- gamification.py
- Dockerfile
- railway.toml
- requirements.txt（略調整）

### 改寫重點

**utils.py** — 把城市正規化換成科目正規化：
```python
SUBJECTS = {
    "行政法概要": ["行政法", "行政法概要"],
    "刑法概要": ["刑法", "刑法概要"],
    "刑事訴訟法概要": ["刑訴", "刑事訴訟法概要", "刑事訴訟法"],
    "法院組織法": ["法院組織法", "法組"],
    "法學知識與英文": ["法學知識", "法學知識與英文"],
    "國文": ["國文"],
}
QUESTION_TYPES = {"mcq": "選擇題", "essay": "申論題"}
```

**main.py** — 主要路由改動：
- `/api/questions` filter：改 `subject` 取代 `city`
- `/api/stats` 改為按科目統計
- 新增 `/api/subjects` endpoint

**app.js** — UI 改動：
- 科目篩選器（取代縣市）
- 題型篩選（選擇/申論）
- 申論題：不顯示選項，只顯示題幹 + 參考解答

### 新增功能
- 體能測驗標準靜態頁（男5'50"/女6'20"）
- 申論題閱讀模式（展開/收合參考解答）

---

## 資料 Schema（questions.json）

```json
{
  "id": "113_行政法概要_1",
  "year": 2024,
  "roc_year": 113,
  "subject": "行政法概要",
  "exam_type": "司法特考",
  "exam_level": "四等",
  "exam_category": "法警",
  "question_number": 1,
  "type": "mcq",
  "stem": "題幹文字...",
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "answer": "A",
  "explanation": "解析文字...",
  "source": "法源法律網",
  "source_eid": "7634"
}
```

---

## 快速參考

- Phase 1 偵查報告：`docs/phase1-recon.md`
- 法源 EID（113年）：7634(行政法), 7635(法院組織法), 7636(刑法), 7637(刑訴)
- 法源 EID（114年）：8007(行政法), 8008(法院組織法), 8009(刑法), 8010(刑訴)
- 公職王 113年 PDF：docs/phase1-recon.md 內有完整直連 URL
- exam-analyzer 路徑：`C:\Users\denni\exam-analyzer\`
- 部署目標：Railway（同 exam-analyzer）
