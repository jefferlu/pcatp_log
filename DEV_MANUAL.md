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
├── app.py                    # Streamlit 主入口
├── pages/                    # Multi-page 頁面
│   ├── 01_Session_Overview.py    # Session 彙總總覽
│   ├── 02_Loop_Detail.py         # 單一 Loop 詳細結果
│   └── 03_Comparison.py          # 多 Loop / Session 比較
├── components/               # 可重用 UI 元件
│   ├── __init__.py
│   ├── metrics_card.py           # PASS/FAIL/BLOCK 統計卡片
│   ├── result_table.py           # 測試結果表格 (帶色彩標示)
│   └── sidebar.py                # 側欄 Session/Loop 選擇器
├── parsers/                  # Log 解析模組
│   ├── __init__.py
│   ├── csv_parser.py             # CSV 結果解析
│   └── log_parser.py             # TestSetResponse.txt 解析
├── utils/                    # 工具函式
│   ├── __init__.py
│   └── helpers.py                # 共用工具 (顏色、格式化等)
├── .streamlit/
│   └── config.toml               # Streamlit 主題設定
├── requirements.txt
└── DEV_MANUAL.md             # 本開發手冊
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
    "loops": {
        1: {
            "results": DataFrame,    # 來自 N_EMM_*.csv
            "log": list[dict],       # 來自 N_EMM_*_TestSetResponse.txt
        },
        ...
    }
}
```
