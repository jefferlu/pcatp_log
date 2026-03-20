# ATP Log 分析系統 開發手冊

> **技術棧**：Python · Streamlit · DuckDB · Pandas · Plotly
> **部署方式**：Docker（Server）/ 本機開發（streamlit run）
> **分支**：`claude/atp-log-analyzer-e2FZE`

---

## 版本開發紀錄

| 版本   | 日期       | Phase   | 內容摘要                                                  |
|--------|------------|---------|-----------------------------------------------------------|
| v0.1.0 | 2026-03-17 | Phase 1 | 初始化 Streamlit infra：目錄結構、入口、parsers、components、設定檔 |

---

## 系統概述

ATP (Acceptance Test Program) Log 分析系統，用於事後重現 ATP 系統即時畫面，支援多次測試 session 的載入、分析與比較。以 DuckDB 為資料庫後端，透過 Docker 部署於 Ubuntu Server，支援多使用者帳號與 Session 共享。

### Log 結構說明

```
session_dir/
├── <任意名稱>.csv               # Session 彙總 CSV（header 無 Test Loop 值）
├── <任意名稱>.csv               # Loop N 結果 CSV（header 含 Test Loop = N）
└── <任意名稱>.txt               # Loop N 的即時執行 log（與 loop CSV 成對）
```

> **檔案分類不依賴檔名格式**，全部以 CSV header 內容判斷（`Test Loop` 欄位有無數值）。

#### CSV 欄位格式 (per-loop)

```
Test ID, Category, Test Name, Sub Item, Result, Value, [Hex ID]
```

- **Result**: `PASS` / `FAIL` / `BLOCK` / 空白（未執行）
- **Value**:
  - 量測範圍：`Min:xxx Max:xxx | Limit[lo~hi]`
  - 離散比對：`Cur:N | Exp:N`
  - Blocked：空白或 `No criteria`

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
│   ├── 02_Loop_Detail.py             # 單一 Loop 詳細結果 + 失敗原因分析
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
│   └── failure_analysis.py           # 失敗原因分析 (CSV ↔ TXT 交叉比對)
├── config/                       # 設定檔 (不進版控)
│   ├── users.yaml                    # 使用者帳號 (bcrypt hash)
│   └── shares.yaml                   # Session 共享設定
├── scripts/
│   ├── create_user.py                # CLI 建立 / 更新使用者
│   └── generate_manual.py            # 產生使用者手冊 PDF
├── .document/                    # 文件目錄 (與程式開發無關)
│   ├── atplog_dev_manual.md          # 開發手冊（本文件）
│   └── atplog_user_manual.md         # 使用手冊
├── .streamlit/
│   └── config.toml                   # Streamlit 主題設定
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── requirements.txt
└── atp_log.duckdb                # 本地資料庫 (runtime 產生，不進版控)
```

---

## 開發 Phase 規劃

### Phase 1 — Infrastructure（已完成）

**目標**：建立可執行的 Streamlit 骨架，所有頁面可正常路由，資料解析 module 有基礎 API。

**產出**：
- `app.py`：首頁 / Session 選擇入口
- `parsers/csv_parser.py`：解析 loop CSV 與 session 彙總 CSV
- `parsers/log_parser.py`：解析 TestSetResponse.txt
- `components/`：metrics_card、result_table、sidebar 骨架
- `utils/helpers.py`：顏色 map、格式化工具
- `.streamlit/config.toml`：主題設定
- `requirements.txt`

---

### Phase 2 — Session Overview Dashboard（已完成）

**目標**：Session 首頁展示整體 PASS/FAIL/BLOCK 統計，類似 ATP 系統的 Summary 畫面。

**已完成功能**：
- Session 選擇下拉（側欄）
- 整體 Summary Card (Total/Passed/Failed/Blocked)
- 每個 Loop 的統計趨勢圖（折線圖）
- 所有 Loop 結果 Heatmap（Test ID × Loop）

---

### Phase 3 — Loop Detail View（已完成）

**目標**：重現每個 Loop 的 ATP 即時畫面。

**已完成功能**：
- Loop 選擇器（側欄）
- 分 Category 的結果表格（帶 PASS/FAIL 顏色，支援 Category / Result 篩選）
- 失敗原因分析（CSV ↔ TXT 交叉比對，詳見失敗原因分析模組章節）
- TestSetResponse log 時間軸（支援 level 篩選）

---

### Phase 4 — Multi-Loop / Cross-Session Comparison（已完成）

**目標**：比較不同 Loop 或不同 Session 的測試結果。

**已完成功能**：
- Loop Comparison：兩 Loop 結果並排對比，列出差異項目
- Session Comparison：狀態翻轉分析（PASS→FAIL 等），Unstable Items 排行，Result Sequence 折線圖

---

### Phase 5 — 進階分析 & 匯出

**目標**：提供深度分析與報表匯出。

**計畫功能**：
- 量測值統計分析（平均、標準差）
- PDF / Excel 報表匯出
- Log 關鍵字搜尋
- 自動異常偵測（量測值離群分析）

---

## 變更紀錄

### 2026-03-20 — ZIP 匯入 Session ID 命名規則調整

**修改檔案**：`pages/00_Upload.py` — `_prepare_zip_sessions()`

**背景**：原本 session ID 固定來自 ZIP 檔名（stem），導致將多個 session 目錄打包成一個 ZIP 上傳時，產生的 session ID 為 `<zip檔名>_<子目錄名>` 而非子目錄本身的名稱。

**新邏輯**（以 CSV 的直接父目錄是否為 ZIP 解壓根目錄來判斷）：

| ZIP 結構 | Session ID 來源 |
|----------|----------------|
| CSV 直接在 ZIP 根目錄（flat） | ZIP 檔名（`zip_stem`）— 行為與修改前相同 |
| CSV 在單一子目錄 | 子目錄名稱（`src_dir.name`）|
| CSV 在多個子目錄（all sessions 打包） | 各子目錄名稱（`src_dir.name`）|

**修改前後對照**：

```
# 修改前
all_sessions.zip / EMM/ → session ID = "all_sessions_EMM"

# 修改後
all_sessions.zip / EMM/ → session ID = "EMM"
```

flat ZIP 行為不受影響：
```
session_20260301.zip / (flat) → session ID = "session_20260301"  ← 不變
```

---

## 開發規範

### 命名規則
- Python 模組：`snake_case`
- Streamlit page 檔名：`NN_PascalCase.py`（NN 為排序號）
- Session ID：來自上傳的 ZIP 檔名（flat）或子目錄名稱（有子目錄時）

### 資料流

```
上傳（ZIP / CSV）
    └── parsers/csv_parser.py + parsers/log_parser.py（解析）
        └── db/importer.py（寫入 DuckDB）
            └── db/database.py（query）
                └── session_data dict / DataFrame
                    └── components/ + utils/（渲染）
                        └── Streamlit UI
```

### Session Data 資料結構
```python
session = {
    "id": "test_20260316163640",
    "summary": DataFrame,        # 來自 session 彙總 CSV（無結果，只有測點清單）
    "header_meta": dict,         # 來自第一個 loop CSV 的 header 欄位
    "loops": {
        1: {
            "header":  dict,         # Test Mode, Test End Time 等
            "results": DataFrame,    # 來自 loop 結果 CSV
            "legacy":  DataFrame,    # 第二段 Test ID 區塊（CAN/LIN legacy rows）
        },
        ...
    }
}
```

---

## 認證與存取控制

### 機制
使用 `streamlit-authenticator`，設定檔位於 `config/users.yaml`（不進版控）。

### 使用者角色

| 角色 | 可見 Session | 刪除權限 |
|------|-------------|---------|
| `admin` | 所有 session | 任意 session |
| `user`  | 自己匯入的 session | 僅自己的 |

### 新增使用者
```bash
python scripts/create_user.py
```

---

## Docker 部署

### 部署流程（Ubuntu Server）
```bash
# 確認 config 目錄存在，放入 users.yaml / shares.yaml
mkdir -p config

# 建立並啟動容器
docker compose up -d --build
```

### 重要路徑

| 路徑 | 說明 |
|------|------|
| `/data/atp_log.duckdb` | DuckDB 資料庫（named volume `atp-data` 持久化） |
| `/app/config/` | 設定檔（bind mount `./config`，可直接在 host 編輯）|

### 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `ATP_DATA_DIR` | `/data` | DuckDB 存放目錄 |

---

## 失敗原因分析模組

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

| 條件 | 分類 |
|------|------|
| Result = BLOCK / BLOCKED | `Blocked` |
| type = range，max > hi_limit | `Out of Range (High)` |
| type = range，min < lo_limit | `Out of Range (Low)` |
| type = range，兩端皆超出 | `Out of Range (Both)` |
| type = compare，cur ≠ exp | `Value Mismatch` |
| CAN category + log 有 "No CAN result found" | `No Response` |
| 其他 | `Unknown` |

#### 失敗類別說明

**`Out of Range (High)`**
量測最大值超過規格上限（max_val > hi_limit）。代表訊號電壓／電流偏高。
```
範例：Actual 5000.0 ~ 5000.0  Limit 4151.0 ~ 4588.0
      max(5000) > hi_limit(4588) → 超上限
```

**`Out of Range (Low)`**
量測最小值低於規格下限（min_val < lo_limit）。代表訊號電壓／電流偏低。
```
範例：Actual 216.0 ~ 232.0  Limit 3128.0 ~ 3920.0
      min(216) < lo_limit(3128) → 低於下限
```

**`Out of Range (Both)`**
最小值低於下限且最大值超過上限，量測值橫跨整個規格範圍。
通常代表訊號在 loop 期間大幅震盪，或取樣時段過長導致極值同時觸碰兩端。

**`Out of Range`**
Value 欄為 range 格式，但解析後數值看起來在範圍內卻被標為 FAIL。
可能原因：測試程式端有額外判斷條件、Value 欄資料不完整或浮點數誤差。
發生時需回頭查 Log Evidence 欄確認。

**`Blocked`**
該測試項目未執行，因前置條件不滿足。
Log Evidence 欄會顯示對應的 `[PROC]` 訊息，說明是哪個硬體未連接或哪個前置步驟未完成。
```
範例：CR1001 not connected. Skipping SLAC Handshake Test.
```

**`Value Mismatch`**
離散數值格式（`Cur:X | Exp:Y`），實際值與預期值不符（cur_val ≠ exp_val）。
常見於 CAN error count、state register 等數位量的比對。

**`No Response`**
TXT log 出現 `No CAN result found, treat as FAIL`，
代表測試期間未收到 CAN 回應封包，通道沒有任何資料。

**`Unknown`**
Value 欄格式無法解析（空白或非標準格式），且無法從 log 補充資訊。

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

依失敗類別取得對應的 log 佐證：

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
| `Root Cause` | 失敗類別（文字，如 `Out of Range (High)`）|
| `Actual` | 實際量測值（見下方說明）|
| `Limit` | 規格限制範圍（見下方說明）|
| `Deviation` | 偏差百分比（如 `+15.2%` / `-3.1%`）|
| `Log Evidence` | 佐證 log 訊息（來自 TXT）|

#### Actual / Limit 欄位說明

**Range 格式**（CSV Value: `Min:2508.00 Max:2529.00 | Limit[3128~3920]`）

| 欄位 | 值 | 意義 |
|------|----|------|
| `Actual` | `2508.0 ~ 2529.0` | loop 期間 UDP Data 取樣的**最小值 ~ 最大值** |
| `Limit`  | `3128.0 ~ 3920.0` | 測試規格定義的**合格範圍下限 ~ 上限** |
| `Deviation` | `+X%` / `-X%` | 超出上限時為正值，低於下限時為負值 |

**Compare 格式**（CSV Value: `Cur:0 | Exp:0`）

| 欄位 | 值 | 意義 |
|------|----|------|
| `Actual` | `0` | 實際讀取到的離散數值（error count、state 等）|
| `Limit`  | `Exp: 0` | 預期應符合的值 |

**Fallback（CSV Value 為空）**

若 CSV `Value` 欄為空，`Actual` 欄改從 TXT log 的 `[UDP Data]` 行補充：
```
Actual: Cur:X Avg:X Min:X Max:X    ← 來自 TXT，格式與 range 不同
```
此情況下 `Limit` 欄為空，需人工對照規格文件。

### 顯示常數

`ROOT_CAUSE_COLOR`：各失敗類別的顏色代碼（用於 badge 背景）
`ROOT_CAUSE_ICON`：各失敗類別的符號（↑ ↓ ↕ ≠ — ⊘ ?）
