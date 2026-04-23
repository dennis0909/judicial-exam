# Phase 1 偵查報告 — 法警特考考古題系統

> 建立時間：2026-04-23
> 下個 session 直接讀這份，不需重做偵查

---

## 專案目標

建立「司法特考四等法警考古題分析系統」，功能與架構比照 `C:\Users\denni\exam-analyzer\`（幼教教師甄試系統），主題改為法警特考。

## 考試科目（司法四等法警）

| 科目 | 題型 | 題數 |
|------|------|------|
| 國文（作文80%+測驗20%） | 混合 | — |
| 法學知識與英文（憲法30%+法學緒論30%+英文40%） | 選擇 | 30題 |
| 行政法概要 | 選擇 | 50題 |
| 刑法概要 | 選擇 | 50題 |
| 法院組織法 | 申論 | 4題 |
| 刑事訴訟法概要 | 申論 | 4題 |
+ 體能複試（1200公尺跑走，男≤5分50秒，女≤6分20秒）

---

## 資料源評估結果

### ✅ 最佳：法源法律網（lawbank.com.tw）

- **URL**：`https://www.lawbank.com.tw/exam/queryresult.aspx?CT=B&Grp=%E6%B3%95%E8%AD%A6&PageNo=1`
- 共 13 頁，122 題（含解析）
- 按年度/科目分類，EID 規律整數
- **含正確答案和解析** ✅
- 無需登入，HTTP 直接可爬

**已確認的 EID：**

| 年份 | 行政法概要 | 法院組織法 | 刑法概要 | 刑事訴訟法概要 |
|------|-----------|-----------|---------|---------------|
| 114年 | 8007 | 8008 | 8009 | 8010 |
| 113年 | 7634 | 7635 | 7636 | 7637 |
| 112年 | 7378 | 7386 | 需翻頁 | 需翻頁 |
| 111年 | — | — | 6961 | — |
| 86年  | — | 1838 | — | — |

個別試題 URL：`https://www.lawbank.com.tw/exam/exam.aspx?EID=7634`

---

### ✅ 備選：公職王 PDF（public.com.tw）

113年 PDF 直連（已驗證可下載）：
```
https://www.public.com.tw/TestFileManage/21088/anspdf/113司法四等-行政法概要.pdf
https://www.public.com.tw/TestFileManage/21090/anspdf/113司法特考四等-刑法概要.pdf
https://www.public.com.tw/TestFileManage/21071/anspdf/113司法四等-刑事訴訟法概要.pdf
https://www.public.com.tw/TestFileManage/21078/anspdf/113司法特考四等-法院組織法.pdf
https://www.public.com.tw/TestFileManage/21069/anspdf/113司法特考四等-國文(作文與測驗).pdf
https://www.public.com.tw/TestFileManage/21093/anspdf/113司法特考四等、海巡特考四等-法學知識與英文.pdf
```

其他年份需從以下頁面找連結：
- `https://www.public.com.tw/exampoint/2024-judicial`（114年）
- `https://www.public.com.tw/exampoint/2023-judicial`（113年）
- `https://www.public.com.tw/exampoint/2022-judicial`（112年）

---

### ⚠️ 補充：yamol.tw（阿摩）

- robots.txt 允許爬蟲（除 Bingbot）
- **題幹可爬，但答案不可見**（JS 渲染或需登入）
- 分頁格式：`https://yamol.tw/cat-{encoded_name}-{catid}.htm?page=N`

**法警相關試卷（刑事訴訟法概要 catid=87）：**

| 年份 | exam ID | URL |
|------|---------|-----|
| 114 | 130173 | `https://yamol.tw/exam-114年++114+司法特種考試_四等_法警：刑事訴訟法概要130173-130173.htm` |
| 113 | 121998 | `https://yamol.tw/exam-113年++113+司法特種考試_四等_法警：刑事訴訟法概要121998-121998.htm` |
| 112 | 116113 | `https://yamol.tw/exam-112年++112+司法特種考試_四等_法警（男）、法警（女）：刑事訴訟法概要1-116113.htm` |
| 112 | 116438 | `https://yamol.tw/exam-112年++112+原住民族特種考試_四等_法警：刑事訴訟法概要116438-116438.htm` |
| 111 | 110249 | `https://yamol.tw/exam-111年++111+司法特種考試_四等_法警：刑事訴訟法概要110249-110249.htm` |
| 111 | 110661 | `https://yamol.tw/exam-111年++111+原住民族特種考試_四等_法警：刑事訴訟法概要110661-110661.htm` |
| 109 | 90013  | `https://yamol.tw/exam-109年++109+司法特種考試_四等_法警：刑事訴訟法概要90013-90013.htm` |
| 109 | 90851  | `https://yamol.tw/exam-109年++109+原住民族特種考試_四等_法警：刑事訴訟法概要90851-90851.htm` |
| 108 | 78549  | `https://yamol.tw/exam-108年++108+司法特種考試_四等_法警：刑事訴訟法概要78549-78549.htm` |
| 108 | 79032  | `https://yamol.tw/exam-108年++108+原住民族特種考試_四等_法警：刑事訴訟法概要79032-79032.htm` |
| 107 | 74223  | `https://yamol.tw/exam-107年++107+司法特種考試_四等_法警：刑事訴訟法概要74223-74223.htm` |
| 107 | 71826  | `https://yamol.tw/exam-107年++107+原住民族特種考試_四等_法警：刑事訴訟法概要71826-71826.htm` |
| 103 | 43280  | `https://yamol.tw/exam-103年++103+司法特種考試_四等_法警：刑事訴訟法概要43280-43280.htm` |
| 103 | 43283  | `https://yamol.tw/exam-103年++103+原住民族特種考試_四等_法警：刑事訴訟法概要43283-43283.htm` |
| 102 | 44550  | `https://yamol.tw/exam-102年++102+司法特種考試_四等_法警：刑事訴訟法概要44550-44550.htm` |
| 101 | 44379  | `https://yamol.tw/exam-101年++101+原住民族特種考試_四等_法警：刑事訴訟法概要44379-44379.htm` |
| 100 | 45633  | `https://yamol.tw/exam-100年++100+司法特種考試_四等_法警：刑事訴訟法概要45633-45633.htm` |
| 100 | 45402  | `https://yamol.tw/exam-100年++100+原住民族特種考試_四等_法警：刑事訴訟法概要45402-45402.htm` |
| 99  | 46635  | `https://yamol.tw/exam-99年++992+司法特種考試_四等_法警：刑事訴訟法概要46635-46635.htm` |
| 99  | 46574  | `https://yamol.tw/exam-99年++99+原住民族特種考試_四等_法警：刑事訴訟法概要46574-46574.htm` |
| 97  | 48599  | `https://yamol.tw/exam-97年++972+司法特種考試_四等_法警：刑事訴訟法概要48599-48599.htm` |
| 96  | 52283  | `https://yamol.tw/exam-96年++96+原住民族特種考試_四等_法警：刑事訴訟法概要52283-52283.htm` |

**法警行政法概要（catid=777）exam IDs：**
130170(114), 122075(113), 116193(112), 116417/116425(112原民),
103179(110), 90048(109), 64697(106原民), 43165(104), 48604(97-2)

---

### ❌ 不可用

| 來源 | 問題 |
|------|------|
| moex.gov.tw | SSL 憑證失敗，需 Python requests verify=False |
| ting-wen.com | SSL 憑證不符，所有子域失敗 |
| 高鋒公職 PDF | 直連 403 |

---

## Phase 2 執行計畫

### Step 1：執行 scraper_lawbank.py
```bash
cd C:\Users\denni\judicial-exam
python scripts/scraper_lawbank.py
# 輸出：data/lawbank_questions.json（預計 ~500-700 題含解析）
```

### Step 2：執行 scraper_public_pdf.py
```bash
python scripts/scraper_public_pdf.py
# 輸出：data/pdfs/ 目錄 + data/pdf_index.json
```

### Step 3：Phase 3（新 Session）
- 讀取 data/lawbank_questions.json
- Fork exam-analyzer → judicial-exam
- 領域適配（城市→科目, 幼教→法警）
- 申論題模式支援

---

## App 架構（對照 exam-analyzer）

| exam-analyzer | judicial-exam | 說明 |
|--------------|---------------|------|
| 城市（11縣市）| 科目（6科）   | utils.py 正規化層 |
| 幼教5大領域   | 申論/選擇題型  | 題型分類 |
| 考卷年份      | 考卷年份+考試別（司法/原民）| |
| 3257題        | 預計 500-1000題 | 起步，可持續增加 |

**可直接複用：** auth_firebase.py, db.py, gamification.py, Dockerfile, railway.toml, adaptive_engine.py
**需改寫：** utils.py, main.py（路由）, static/index.html, static/js/app.js
**新增：** 申論題閱讀模式, 體能測驗標準頁面
