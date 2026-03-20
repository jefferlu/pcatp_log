# ATP Log 分析系統 開發手冊

> **技術棧**：Python · Streamlit · Pandas · Plotly
> **Log 來源**：`.log_files/<session_id>/`
> **分支**：`claude/atp-log-analyzer-e2FZE`

---

## 版本開發紀錄

| 版本   | 日期       | Phase   | 內容摘要                                                  |
|--------|------------|---------|-----------------------------------------------------------|
| v0.1.0 | 2026-03-17 | Phase 1 | 初始化 Streamlit infra：目錄結構、入口、parsers、components、設定檔 |

---

## 系統概述

ATP (Acceptance Test Program) Log 分析系統，用於事後重現 ATP 系統即時畫面，支援多次測試 session 的載入、分析與比較。

### Log 結構說明

```
.log_files/
└── test_<timestamp>/                  # 一個測試 session
    ├── test_<timestamp>.csv           # Session 彙總 (所有 100 test items)
    ├── TestSetResponse.txt            # Session 整體系統 log
    ├── <N>_EMM_test_<timestamp>.csv        # 第 N loop 測試結果 (PASS/FAIL/BLOCK)
    └── <N>_EMM_test_<timestamp>_TestSetResponse.txt  # 第 N loop 詳細 log
```

#### CSV 欄位格式 (per-loop)

```
Test ID, Category, Test Name, Sub Item, Result, Value, [Hex ID]
```

- **Result**: `PASS` / `FAIL` / `BLOCK` / 空白(未執行)
- **Value**:
  - 量測值：`Min:xxx Max:xxx | Limit[lo~hi]`
  - 數位值：`Raw:HH-HH-HH | Exp:N`
  - Blocked：`Raw:... | No criteria`

#### TestSetResponse.txt 關鍵欄位

```
[HH:MM:SS] [MODULE] message
```

模組包含：`System`, `MQTT`, `DoIP`, `UDS`, `PROC`, `Info`, `CAN`, `LIN`, `UDP Data`, `FAIL`, `PING6`

---

## 專案目錄結構

```
pcatp_log/
├── app.py                        # Streamlit 主入口 + 登入驗證
├── pages/                        # Multi-page 頁面
│   ├── __init__.py                   # 空檔；防止 Streamlit 自動掃描 pages/
│   ├── 00_Upload.py                  # 匯入 Session (ZIP / CSV)
│   ├── 01_Session_Overview.py        # Session 彙總總覽
│   ├── 02_Loop_Detail.py             # 單一 Loop 詳細結果 + 失敗根因分析
│   └── 03_Comparison.py              # 多 Loop / Session 比較
├── components/                   # 可重用 UI 元件
│   ├── __init__.py
│   ├── metrics_card.py               # PASS/FAIL/BLOCK 統計卡片
│   ├── result_table.py               # 測試結果表格 (帶色彩標示)
│   └── sidebar.py                    # 側欄 Session/Loop 選擇器
├── parsers/                      # Log 解析模組
│   ├── __init__.py
│   ├── csv_parser.py                 # CSV 結果解析 (內容分類，不依賴檔名)
│   └── log_parser.py                 # TestSetResponse.txt 解析
├── db/                           # 資料庫層
│   ├── database.py                   # DuckDB schema / CRUD / 存取控制
│   └── importer.py                   # 將解析結果寫入 DuckDB
├── utils/                        # 工具函式
│   ├── __init__.py
│   ├── helpers.py                    # 共用工具 (顏色、格式化等)
│   ├── chart_theme.py                # Plotly 圖表通用樣式
│   └── failure_analysis.py           # 失敗根因分析 (CSV ↔ TXT 交叉比對)
├── config/                       # 設定檔 (不進版控)
│   ├── users.yaml                    # 使用者帳號 (bcrypt hash)
│   └── shares.yaml                   # Session 共享設定
├── scripts/
│   └── create_user.py                # CLI 建立 / 更新使用者
├── .streamlit/
│   └── config.toml                   # Streamlit 主題設定
├── atp_log.duckdb                # 本地資料庫 (runtime 產生，不進版控)
├── requirements.txt
└── DEV_MANUAL.md                 # 本開發手冊
```

---

## 開發 Phase 規劃

### Phase 1 — Infrastructure（目前）

**目標**：建立可執行的 Streamlit 骨架，所有頁面可正常路由，資料解析 module 有基礎 API。

**產出**：
- `app.py`：首頁 / Session 選擇入口
- `parsers/csv_parser.py`：解析 `*_EMM_*.csv` 與 `test_*.csv`
- `parsers/log_parser.py`：解析 `*_TestSetResponse.txt`
- `components/`：metrics_card、result_table、sidebar 骨架
- `utils/helpers.py`：顏色 map、格式化工具
- `.streamlit/config.toml`：深色主題
- `requirements.txt`

---

### Phase 2 — Session Overview Dashboard

**目標**：Session 首頁展示整體 PASS/FAIL/BLOCK 統計，類似 ATP 系統的 Summary 畫面。

**計畫功能**：
- Session 選擇下拉（側欄）
- 整體 Summary Card (Total/Passed/Failed/Blocked)
- 每個 Loop 的統計趨勢圖 (折線圖)
- 測試 Category 分類圓餅圖
- 所有 Loop 結果 Heatmap (Test ID × Loop)

---

### Phase 3 — Loop Detail View

**目標**：重現每個 Loop 的 ATP 即時畫面，對應 `img_files` 截圖。

**計畫功能**：
- Loop 選擇器（側欄）
- 分 Category 的結果表格（帶 PASS/FAIL 顏色）
- 每個 Test Item 的量測值視覺化（量測值 vs 上下限）
- TestSetResponse log 時間軸檢視
- UDP Data 數值走勢圖

---

### Phase 4 — Multi-Loop / Cross-Session Comparison

**目標**：比較不同 Loop 或不同 Session 的測試結果。

**計畫功能**：
- 多 Loop 結果並排對比
- 跨 Session 比較（選取 2+ Session）
- 失敗項目交集分析
- 量測值趨勢跨 Loop 追蹤

---

### Phase 5 — 進階分析 & 匯出

**目標**：提供深度分析與報表匯出。

**計畫功能**：
- 量測值統計分析（平均、標準差）
- 失敗根因分類建議
- PDF / Excel 報表匯出
- Log 關鍵字搜尋
- 自動異常偵測（量測值離群分析）

---

## 開發規範

### 命名規則
- Python 模組：`snake_case`
- Streamlit page 檔名：`NN_PascalCase.py`（NN 為排序號）
- Session folder：`test_<YYYYMMDDHHMMSS>`

### 資料流
```
.log_files/
    └── parsers/ (解析)
        └── session_data dict / DataFrame
            └── components/ (渲染)
                └── Streamlit UI
```

### Session Data 資料結構
```python
session = {
    "id": "test_20260316163640",
    "summary": DataFrame,        # 來自 test_*.csv (無結果，只有清單)
    "header_meta": dict,         # 來自第一個 loop CSV 的 header 欄位
    "loops": {
        1: {
            "header":  dict,         # Test Mode, Test End Time 等
            "results": DataFrame,    # 來自 N_EMM_*.csv
            "legacy":  DataFrame,    # 第二段 Test ID 區塊 (CAN/LIN legacy rows)
        },
        ...
    }
}
```

---

## 失敗根因分析模組

### 概述

`utils/failure_analysis.py` 提供 `analyze_failures(results_df, log_entries)` 函式，
將 CSV 結果中每一筆 FAIL / BLOCK 項目與對應的 TXT log entries 交叉比對，
自動分類失敗原因並補充實際量測值。

### CSV ↔ TXT 連結方式

| 連結鍵 | CSV 欄位 | TXT log 欄位 |
|--------|----------|-------------|
| 訊號 Hex ID | `Hex ID`（如 `0x45`） | `[UDP Data] ID:45 (...)` |
| 訊號名稱 | `Test Name` | `[FAIL] CCS-S2 (0x45): ...` |
| 通道名稱 | `Sub Item` / `Test Name` | `[CAN] FAIL detected (CAN03--)` |

### Value 欄位格式解析

CSV `Value` 欄位有兩種格式，由 `_parse_value()` 負責解析：

```
# 量測範圍格式
Min:2508.00 Max:2529.00 | Limit[3128~3920]
  → type = "range"
  → min_val, max_val, lo_limit, hi_limit

# 離散比對格式
Cur:0 | Exp:0
  → type = "compare"
  → cur_val, exp_val
```

### 根因分類規則

`_classify_root_cause()` 依以下優先順序判斷：

| 條件 | 根因類別 |
|------|---------|
| Result = BLOCK / BLOCKED | `Blocked` |
| type = range，max > hi_limit | `Out of Range (High)` |
| type = range，min < lo_limit | `Out of Range (Low)` |
| type = range，兩端皆超出 | `Out of Range (Both)` |
| type = compare，cur ≠ exp | `Value Mismatch` |
| CAN category + log 有 "No CAN result found" | `No Response` |
| 其他 | `Unknown` |

### Log 索引建立（`_build_log_index`）

掃描 log entries，建立以下查詢表：

```
udp          : { HEX_ID → { name, cur, avg, min, max } | { name, raw } }
fail_msgs    : { HEX_ID → "Out of Range" 等原因字串 }
retry        : { channel → 最大重試次數 }
no_response  : [ "No CAN result found, ..." 訊息列表 ]
blocked_proc : [ "CR1001 not connected. Skipping ..." 訊息列表 ]
```

對應的 TXT log module：

| Module | 用途 |
|--------|------|
| `UDP Data` | 實際量測值（Cur/Avg/Min/Max 或 RawData） |
| `FAIL` | 失敗原因字串，含 Hex ID |
| `CAN` | No Response 或 retry 記錄 |
| `PROC` | Blocked 的前置條件失敗訊息 |

### Log Evidence 補充邏輯

依根因類別取得對應的 log 佐證：

```
Blocked      → blocked_proc[0]（第一個 PROC skip 訊息）
No Response  → no_response[0]
其他 FAIL    → fail_msgs[hex_id]（依 Hex ID 精確比對）
CAN 類別     → 若 retry 記錄中 channel 符合，在前方加上 "Retried N×;"
```

若 CSV `Value` 欄為空，額外從 `udp[hex_id]` 補充 Cur/Avg/Min/Max。

### 輸出欄位

`analyze_failures()` 回傳 DataFrame，欄位如下：

| 欄位 | 說明 |
|------|------|
| `Test ID` | 測試項目編號 |
| `Category` | 測試分類 |
| `Test Name` | 測試名稱 |
| `Sub Item` | 子項目 |
| `Root Cause` | 根因類別（文字，如 `Out of Range (High)`）|
| `Actual` | 實際量測值（`X ~ Y` 或 `Cur:X`）|
| `Limit` | 限制範圍（`A ~ B` 或 `Exp:Y`）|
| `Deviation` | 偏差百分比（如 `+15.2%` / `-3.1%`）|
| `Log Evidence` | 佐證 log 訊息（來自 TXT）|

### 顯示常數

`ROOT_CAUSE_COLOR`：各根因類別的顏色代碼（用於 badge 背景）
`ROOT_CAUSE_ICON`：各根因類別的符號（↑ ↓ ↕ ≠ — ⊘ ?）
