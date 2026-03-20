# ATP Log Analyzer 使用者操作手冊

**User Operation Manual｜版本 1.1｜2026**

---

## 目錄

1. 系統概述
2. 登入
3. 匯入資料（Import Sessions）
4. 側邊欄操作
5. 首頁（Home）
6. Session Overview
7. Loop Detail
8. Comparison
9. 常見問題（FAQ）

---

## 1. 系統概述

ATP Log Analyzer 是一套部署於網頁伺服器的測試記錄分析工具，
專為 ATP（Automated Test Program）系統產生的 CSV 與 TXT log 檔案設計。
透過瀏覽器存取，支援多使用者帳號登入，每位使用者管理自己的測試 session，
並可由管理者授權共享。

### 1.1 主要功能

- **登入驗證**：帳號密碼登入，角色分為管理者（admin）與一般使用者（user）
- **匯入 log**：上傳 ZIP 或 CSV 格式的 ATP log 至伺服器資料庫
- **Session Overview**：趨勢折線圖、Donut 圓餅圖、Result Heatmap
- **Loop Detail**：測試結果表格（含篩選）、失敗原因分析、Log Timeline
- **Comparison**：兩 Loop 比較、Session 狀態翻轉分析

### 1.2 系統需求

| 項目 | 規格 |
|------|------|
| 存取方式 | 瀏覽器（Chrome、Edge、Firefox 任一現代瀏覽器）|
| 網路 | 需連線至伺服器（公司內網或 VPN）|
| 帳號 | 由管理者建立 |

---

## 2. 登入

開啟瀏覽器，前往：**https://atplog.coderun.cc/**

### 2.1 登入步驟

1. 在登入頁面輸入**帳號**（Username）與**密碼**（Password）
2. 點擊 **Login** 按鈕
3. 驗證成功後自動進入系統首頁

> 帳號輸入錯誤時顯示「帳號或密碼錯誤」，請確認帳號後重試。

### 2.2 登出

點擊側邊欄上方的 **登出** 按鈕，頁面返回登入畫面。

### 2.3 使用者角色

| 角色 | 可見 Session | 刪除權限 |
|------|-------------|---------|
| 管理者（admin） | 所有使用者的 session | 任意 session |
| 一般使用者（user） | 自己匯入 + 被共享的 session | 僅自己匯入的 |

---

## 3. 匯入資料（Import Sessions）

在側邊欄點選 **Import Sessions** 進入匯入頁面。

### 3.1 支援格式

| 格式 | 說明 |
|------|------|
| ZIP | 將整個 session 資料夾壓縮成 zip，可包含多個 session |
| CSV（多選）| 直接選取同一 session 的所有 .csv 檔案 |

### 3.2 ATP Log 檔案結構

每個 session 資料夾包含以下成對檔案：

| 檔案 | 說明 |
|------|------|
| Session 總表 .csv | 不含 loop 編號的 CSV，為測點清單（無結果欄位）|
| Loop 結果 .csv | Loop N 的最終測試結果（PASS/FAIL/BLOCK），header 含 Test Loop 欄位 |
| Log .txt | Loop N 的即時執行 log（與 Loop 結果 CSV 成對）|

> 系統以 CSV 檔案的 header 內容（是否含 Test Loop 欄位）判斷檔案類型，
> 不限制檔案命名格式，支援 EMM、IMM 等各種測試模式。

### 3.3 匯入步驟

1. 點選 **Upload Log Files** 區塊中的「Choose file(s)」
2. 選取 ZIP 或多個 CSV 檔案
3. 確認 **Overwrite if session already exists**（預設勾選）
4. 點擊右側 **Import** 按鈕，等候進度條完成
5. 成功後出現綠色提示，session 自動加入側邊欄選單

### 3.4 已匯入 Session 管理

頁面下方 **Imported Sessions** 列出目前可見的所有 session：

- 顯示：Session ID、Test Mode、Loop 數量、匯入時間
- 管理者另外顯示 Owner（擁有者帳號）
- 點擊 **Delete** 可刪除該 session 的所有資料（需有刪除權限）

---

## 4. 側邊欄操作

所有分析頁面共用同一側邊欄，包含以下元素：

| 元素 | 說明 |
|------|------|
| 使用者名稱 | 顯示目前登入帳號，管理者附加 `admin` 標籤 |
| **登出** 按鈕 | 登出系統 |
| Test Session | 下拉選單，選擇要分析的 session（依匯入時間排序）|
| Loop | 下拉選單（僅 Loop Detail 頁出現），選擇單一 loop 查看詳情 |
| Session info | 顯示 Session ID、已載入 loop 數、Test Mode |

> 切換 Session 後，所有頁面自動更新為新 session 的資料。

---

## 5. 首頁（Home）

提供目前選取 session 的總覽資訊。

### 5.1 Session 基本資訊

- **Session ID**：唯一識別碼
- **Test Mode**：測試模式（如 EMM、IMM 等）
- **Total Loops**：本 session 共有幾個 loop

### 5.2 Aggregate Summary

彙總所有 loop 的 PASS / FAIL / BLOCK / Total 計數。

### 5.3 Per-Loop Summary 表格

列出每個 loop 的結束時間、測試總數及 PASS / FAIL / BLOCK 數量，
方便快速比較各 loop 的整體表現。

---

## 6. Session Overview

以圖表形式呈現整個 session 的測試趨勢與分布。

### 6.1 Pass / Fail / Block Trend

折線圖顯示每個 loop 的 PASS（綠）/ FAIL（紅）/ BLOCK（橙）數量變化，
可快速識別哪個 loop 發生異常。

### 6.2 Loop Breakdown（Donut 圓餅圖）

以首個 loop 為例，顯示 PASS / FAIL / BLOCK 的比例分布。

### 6.3 Result Heatmap

X 軸為 Loop 編號，Y 軸為 Test ID，顏色代表各 loop 的結果：

| 顏色 | 結果 |
|------|------|
| 綠色 | PASS |
| 紅色 | FAIL |
| 橙色 | BLOCK |

可快速識別哪些測點在多個 loop 中持續失敗（整列紅色）。

---

## 7. Loop Detail

查看單一 loop 的詳細測試結果、失敗原因分析與執行 log。先在側邊欄選擇 Loop 編號。

### 7.1 Summary Metrics

顯示該 loop 的 Total / Passed / Failed / Blocked 計數及百分比。

### 7.2 Test Results 表格

列出所有測點的詳細結果，支援兩種篩選器：

| 篩選器 | 說明 |
|--------|------|
| Category | 依測試類別篩選（如 CAN Error、Interlock Feedback）|
| Result | 依結果篩選（PASS / FAIL / BLOCK / 全部）|

### 7.3 失敗原因分析

自動交叉比對 CSV 測試結果與 TXT log，針對每一筆 FAIL / BLOCK 項目提供失敗原因分類與量測佐證。

#### 運作方式

系統以 CSV 結果中的 `Hex ID` 欄（如 `0x45`）作為連結鍵，對應 TXT log 中的
`[UDP Data] ID:45` 量測紀錄與 `[FAIL]` 原因訊息，進行精確比對。
CAN 類別的測試另外比對 retry 紀錄與 No Response 訊息。

#### 頂部統計

以色塊 badge 顯示各失敗類別的數量，方便快速掌握本 loop 的失敗分布。

#### 詳細表格欄位

| 欄位 | 說明 |
|------|------|
| ID | 測試項目編號 |
| Category | 測試分類 |
| Test Name | 測試名稱 |
| Sub Item | 子項目 |
| Root Cause | 失敗類別（見下方說明）|
| Actual | 實際量測值（見 Actual / Limit 說明）|
| Limit | 規格限制範圍或預期值（見 Actual / Limit 說明）|
| Dev | 偏差百分比（如 `+15.2%` 表示超上限 15.2%）|
| Log Evidence | 來自 TXT log 的佐證訊息 |

#### 失敗類別說明

**`Out of Range (High)`**
量測最大值超過規格上限（max > 上限），代表訊號電壓／電流**偏高**。
```
範例：Actual 5000.0 ~ 5000.0   Limit 4151.0 ~ 4588.0
      最大值 5000 > 上限 4588 → 超上限
```

**`Out of Range (Low)`**
量測最小值低於規格下限（min < 下限），代表訊號電壓／電流**偏低**。
```
範例：Actual 216.0 ~ 232.0   Limit 3128.0 ~ 3920.0
      最小值 216 < 下限 3128 → 低於下限
```

**`Out of Range (Both)`**
最小值低於下限且最大值超過上限，量測值橫跨整個規格範圍。
通常代表訊號在 loop 期間**大幅震盪**，或取樣時段過長導致極值同時觸碰兩端。

**`Out of Range`**
CSV 標記為 FAIL，但數值看起來在規格範圍內。
可能原因：測試程式有額外的判斷條件，或 Value 欄資料不完整。
建議查看 **Log Evidence** 欄的 TXT log 訊息以進一步確認。

**`Value Mismatch`**
離散數值格式（`Cur:X | Exp:Y`），實際讀取值與預期值不符。
常見於 CAN error count、state register 等數位量的比對。

**`No Response`**
TXT log 出現「No CAN result found, treat as FAIL」，
代表測試期間**未收到 CAN 回應封包**，通道完全沒有資料。

**`Blocked`**
測試項目**未執行**，因為前置條件不滿足（如硬體未連接、前一步驟未完成）。
**Log Evidence** 欄會顯示對應的 TXT log 訊息說明具體原因。
```
範例：CR1001 not connected. Skipping SLAC Handshake Test.
```

**`Unknown`**
Value 欄格式無法解析（空白或非標準格式），且 TXT log 中也無法找到對應資訊。
需人工對照規格文件確認。

#### Actual / Limit 欄位說明

欄位內容依 CSV `Value` 欄的格式而異：

**量測範圍格式**（CSV Value: `Min:2508.00 Max:2529.00 | Limit[3128~3920]`）

| 欄位 | 值 | 意義 |
|------|----|------|
| `Actual` | `2508.0 ~ 2529.0` | loop 期間 UDP Data 取樣的**最小值 ~ 最大值** |
| `Limit`  | `3128.0 ~ 3920.0` | 測試規格定義的**合格範圍下限 ~ 上限** |
| `Dev` | `+X%` / `-X%` | 超出上限時為正值，低於下限時為負值 |

**離散比對格式**（CSV Value: `Cur:0 | Exp:1`）

| 欄位 | 值 | 意義 |
|------|----|------|
| `Actual` | `0` | 實際讀取到的數值（error count、state 等）|
| `Limit`  | `Exp: 1` | 預期應符合的值 |

**Fallback（CSV Value 為空）**

若 CSV `Value` 欄為空，`Actual` 欄改從 TXT log 的 `[UDP Data]` 補充：
```
Actual: Cur:X Avg:X Min:X Max:X
```
此情況下 `Limit` 欄為空，需人工對照規格文件確認。

#### Log Evidence 欄說明

| 失敗類別 | Log Evidence 來源 |
|---------|------------------|
| `Blocked` | TXT log 中第一筆 `[PROC]` skip 訊息 |
| `No Response` | TXT log 中第一筆「No CAN result found」訊息 |
| 其他 FAIL | TXT log 中對應 Hex ID 的 `[FAIL]` 訊息 |
| CAN 類別 | 若有 retry 記錄，前方加上「Retried N×;」|

### 7.4 Log Timeline

顯示該 loop 的即時執行記錄，支援以 Log Level 篩選：

| Level | 說明 |
|-------|------|
| fail | 失敗事件（紅色）|
| error | 系統錯誤（橙色）|
| warning | 警告訊息（黃色）|
| pass | 通過事件（綠色）|
| info | 一般資訊（灰色）|

---

## 8. Comparison

提供兩個視角的跨 loop 比較分析，以頁籤切換。

### 8.1 Session Comparison（Session 內翻轉分析）

分析整個 session 中每個測點的完整狀態變化軌跡：

- **Summary Metrics**：總測點數、不穩定測點數、翻轉總次數
- **Transition Types** 長條圖：各類翻轉（PASS→FAIL 等）的次數分布
- **Unstable Items** 表格：翻轉最頻繁的測點排行，含詳細軌跡
- **Result Sequence**：選取單一測點，查看其在所有 loop 的狀態走勢折線圖

> 狀態翻轉以每個 loop 的 CSV 最終結果為準（已包含 retry 後的判定），
> 不會將 retry 過程中的 FAIL 視為翻轉。

### 8.2 Loop Comparison（兩 Loop 比較）

- 從下拉選單分別選取 **Loop A** 和 **Loop B**
- 系統自動比對兩 loop 間結果有差異的測點，列為 **Changed Items**
- 未變動的測點收折在 Expander 中

---

## 9. 常見問題（FAQ）

| 問題 | 解決方式 |
|------|---------|
| 無法開啟登入頁面 | 確認可正常存取網際網路，並再次嘗試開啟 https://atplog.coderun.cc/ |
| 帳號或密碼錯誤 | 聯絡管理者確認帳號，或請管理者重設密碼 |
| No sessions in database | 前往 Import Sessions 頁面先匯入 log 檔案 |
| No loop data found | 確認上傳的 session 中有 loop 結果 CSV（header 含 Test Loop 欄位）|
| 匯入後 0 loop(s) | ZIP 內的 CSV 可能不含 loop 編號（header Test Loop 欄為空），請確認檔案格式 |
| Log Timeline 顯示空白 | 該 loop 無對應的 .txt log 檔案（匯入時未包含，屬正常現象）|
| 失敗原因分析顯示空白 | 該 loop 全數 PASS，無需分析 |
| Heatmap 顯示 Not enough data | 該 session 只有 1 個 loop，無法繪製跨 loop 熱圖 |
| Session Comparison 無資料 | 該 session 所有測點在所有 loop 中結果完全一致 |
