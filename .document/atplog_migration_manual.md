# ATP Log Analyzer 遷移手冊

> **遷移方向**：Streamlit + DuckDB → Angular + Django-Ninja + PostgreSQL
> **建立日期**：2026-03-23
> **狀態**：規劃中

---

## 目錄

1. 遷移背景與目標
2. 現有系統盤點
3. 目標架構
4. 可複用資產清單
5. Phase 1 — Django-Ninja + PostgreSQL 後端
6. Phase 2 — Angular 前端
7. Phase 3 — 正式切換
8. Docker 部署變更
9. 各功能對照表

---

## 1. 遷移背景與目標

### 為什麼遷移

| 問題 | 說明 |
|------|------|
| Streamlit 不適合多人 web | 每個 user session 是獨立 Python thread，狀態管理靠 `session_state` hack |
| 版本發佈困難 | 桌面版需要重新打包派送；Streamlit 無法做細緻前端互動 |
| DuckDB write lock | 多人同時匯入時可能衝突；Django ORM 不原生支援 DuckDB |
| 延展性受限 | 新功能（即時推播、複雜表單、權限細化）在 Streamlit 中難以實現 |

### 遷移目標

- 後端：**Django-Ninja**（Python，複用現有解析邏輯）
- 前端：**Angular**（SPA，完整的元件化與狀態管理）
- 資料庫：**PostgreSQL**（MVCC 並發、Django ORM 原生支援、HA 可擴展）
- 部署：**Docker Compose**（現有架構延伸，加入 PostgreSQL container）

### 遷移原則

1. **後端先行**：Django-Ninja API 完成並驗證後，再動前端
2. **平行運行**：Streamlit 版本在 Angular 完成前持續提供服務
3. **核心邏輯不重寫**：parsers / failure_analysis 原封不動搬入 Django
4. **分階段切換**：功能逐頁完成後切換，不一次全換

---

## 2. 現有系統盤點

### 技術棧

| 層次 | 現有 | 目標 |
|------|------|------|
| 前端 | Streamlit 1.55 | Angular |
| API | 無（Streamlit 直接呼叫 Python）| Django-Ninja |
| 後端邏輯 | Python（parsers / utils）| Python（原封不動）|
| 資料庫 | DuckDB（檔案型）| PostgreSQL |
| 認證 | streamlit-authenticator（YAML）| JWT（Django + djangorestframework-simplejwt）|
| 部署 | Docker（單一 container）| Docker Compose（三個 services）|

### 現有目錄結構（Streamlit 版）

```
pcatp_log/
├── app.py                    ← 不遷移（Streamlit 入口）
├── pages/                    ← 不遷移（轉為 API endpoint 規格參考）
├── components/               ← 不遷移（轉為 Angular 元件參考）
├── parsers/                  ← 直接複用
│   ├── csv_parser.py
│   └── log_parser.py
├── db/
│   ├── database.py           ← 不遷移（改為 Django models）
│   └── importer.py           ← 部分複用（解析邏輯保留，DB 寫入改用 ORM）
├── utils/
│   ├── helpers.py            ← 直接複用
│   ├── chart_theme.py        ← 不遷移（前端圖表改用 ECharts）
│   └── failure_analysis.py   ← 直接複用
└── config/
    ├── users.yaml            ← 不遷移（改用 PostgreSQL 的 users table）
    └── shares.yaml           ← 不遷移（改用 DB 的 session_shares table）
```

### 現有 DuckDB Schema

```sql
sessions       (session_id, owner, imported_at, test_mode, total_loops)
session_shares (session_id, username)
loop_headers   (session_id, loop_num, end_time, test_mode)
results        (session_id, loop_num, test_id, category, test_name, sub_item, result, value, hex_id)
legacy_results (session_id, loop_num, test_id, category, test_name, sub_item, result, value, hex_id)
log_entries    (session_id, loop_num, time_str, module, message, level)
```

---

## 3. 目標架構

```
┌─────────────────────────────────────────────────────┐
│                    Client（瀏覽器）                    │
│                     Angular SPA                      │
└───────────────────────┬─────────────────────────────┘
                        │ HTTPS / JWT
┌───────────────────────▼─────────────────────────────┐
│               Django-Ninja API Server                │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────┐ │
│  │  Auth    │  │  Sessions  │  │  Analysis API    │ │
│  │  /token  │  │  /sessions │  │  /failure-analysis│ │
│  └──────────┘  └────────────┘  └──────────────────┘ │
│                                                      │
│  parsers/csv_parser.py   ← 直接複用                   │
│  parsers/log_parser.py   ← 直接複用                   │
│  utils/failure_analysis.py ← 直接複用                 │
└───────────────────────┬─────────────────────────────┘
                        │ Django ORM
┌───────────────────────▼─────────────────────────────┐
│                    PostgreSQL                        │
└─────────────────────────────────────────────────────┘
```

### Docker Compose 目標結構

```yaml
services:
  db:           # PostgreSQL
  api:          # Django-Ninja
  web:          # Angular（nginx serve）
```

---

## 4. 可複用資產清單

### 直接複用（不需修改）

| 檔案 | 說明 |
|------|------|
| `parsers/csv_parser.py` | CSV 解析邏輯完全與 DB 無關 |
| `parsers/log_parser.py` | TXT log 解析邏輯完全與 DB 無關 |
| `utils/failure_analysis.py` | 輸入 DataFrame + list，輸出 DataFrame，不碰 DB |
| `utils/helpers.py` | 顏色 map、格式化函式 |

### 部分複用（需調整）

| 檔案 | 需要的調整 |
|------|-----------|
| `db/importer.py` | 解析邏輯保留；DB 寫入改為呼叫 Django ORM |
| `config/users.yaml` | 資料遷移至 PostgreSQL users table；YAML 格式廢棄 |
| `config/shares.yaml` | 資料遷移至 PostgreSQL session_shares table |

### 作為規格參考（不複用程式碼）

| 元件 | 對應目標 |
|------|---------|
| `pages/*.py` | Angular 各頁面元件的功能規格 |
| `components/*.py` | Angular 共用元件的 UI 規格 |
| `utils/chart_theme.py` | ECharts / ngx-charts 的圖表樣式規格 |

---

## 5. Phase 1 — Django-Ninja + PostgreSQL 後端

### 目標

建立完整 API，可獨立驗證資料正確性。Streamlit 版本在此階段持續運行，不影響現有用戶。

### 專案結構

```
atplog_api/                   # Django 專案根目錄
├── manage.py
├── atplog_api/               # Django 設定
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── auth/                 # 使用者認證（JWT）
│   │   ├── models.py         # User model
│   │   └── api.py            # /auth/token, /auth/refresh
│   └── sessions/             # 主要業務邏輯
│       ├── models.py         # Django models（對應現有 DuckDB schema）
│       ├── api.py            # API endpoints
│       ├── importer.py       # 從 parsers 複用，改用 ORM 寫入
│       └── analysis.py       # 從 utils/failure_analysis 複用
├── parsers/                  # 直接複製現有 parsers/
├── utils/                    # 直接複製現有 utils/（排除 chart_theme.py）
└── requirements.txt
```

### Django Models（對應 DuckDB schema）

```python
# apps/sessions/models.py

class Session(models.Model):
    session_id  = models.CharField(max_length=255, primary_key=True)
    owner       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    test_mode   = models.CharField(max_length=64, blank=True)
    total_loops = models.IntegerField(default=0)

class SessionShare(models.Model):
    session  = models.ForeignKey(Session, on_delete=models.CASCADE)
    user     = models.ForeignKey(User, on_delete=models.CASCADE)
    class Meta:
        unique_together = ("session", "user")

class LoopHeader(models.Model):
    session   = models.ForeignKey(Session, on_delete=models.CASCADE)
    loop_num  = models.IntegerField()
    end_time  = models.CharField(max_length=32, blank=True)
    test_mode = models.CharField(max_length=64, blank=True)
    class Meta:
        unique_together = ("session", "loop_num")

class Result(models.Model):
    session   = models.ForeignKey(Session, on_delete=models.CASCADE)
    loop_num  = models.IntegerField()
    test_id   = models.IntegerField()
    category  = models.CharField(max_length=128, blank=True)
    test_name = models.CharField(max_length=255, blank=True)
    sub_item  = models.CharField(max_length=255, blank=True)
    result    = models.CharField(max_length=32, blank=True)
    value     = models.TextField(blank=True)
    hex_id    = models.CharField(max_length=16, blank=True)

class LegacyResult(Result):      # 同結構，獨立 table
    class Meta:
        db_table = "legacy_results"

class LogEntry(models.Model):
    session  = models.ForeignKey(Session, on_delete=models.CASCADE)
    loop_num = models.IntegerField()
    time_str = models.CharField(max_length=16, blank=True)
    module   = models.CharField(max_length=64, blank=True)
    message  = models.TextField(blank=True)
    level    = models.CharField(max_length=16, blank=True)
```

### API Endpoints（Django-Ninja）

```
POST   /api/auth/token                  # 登入，取得 JWT
POST   /api/auth/refresh                # 刷新 token

GET    /api/sessions                    # 列出可見 sessions
POST   /api/sessions/import             # 上傳 ZIP / CSV 匯入
DELETE /api/sessions/{session_id}       # 刪除 session

GET    /api/sessions/{session_id}                       # session 基本資訊
GET    /api/sessions/{session_id}/loops                 # 所有 loop 的 header
GET    /api/sessions/{session_id}/loops/{loop_num}/results      # 測試結果
GET    /api/sessions/{session_id}/loops/{loop_num}/log-entries  # log entries
GET    /api/sessions/{session_id}/loops/{loop_num}/failure-analysis  # 失敗原因分析

GET    /api/sessions/{session_id}/overview              # Session Overview 圖表資料
GET    /api/sessions/{session_id}/comparison            # Comparison 資料

GET    /api/admin/users                 # 使用者管理（admin only）
POST   /api/admin/users                 # 新增使用者
POST   /api/admin/shares                # 更新共享設定
```

### 認證機制變更

| 現有 | 目標 |
|------|------|
| streamlit-authenticator（YAML + cookie）| JWT（djangorestframework-simplejwt）|
| config/users.yaml | PostgreSQL users table |
| config/shares.yaml | PostgreSQL session_shares table |
| 角色存在 YAML | Django 的 `is_staff` 或自定義 role field |

### Phase 1 完成標準

- [ ] 所有 API endpoints 可正常回傳資料
- [ ] JWT 認證正常（登入、刷新、過期處理）
- [ ] admin / user 角色權限正確
- [ ] 匯入 ZIP / CSV 功能正常
- [ ] 失敗原因分析 API 回傳結果與 Streamlit 版一致
- [ ] PostgreSQL + Django 跑在 Docker 中
- [ ] 現有 DuckDB 資料可一次性遷移至 PostgreSQL

---

## 6. Phase 2 — Angular 前端

### 目標

建立 Angular SPA，功能對應現有 Streamlit 頁面，全部接 Phase 1 的 Django-Ninja API。

### 專案結構

```
atplog-web/                   # Angular 專案根目錄
├── src/
│   ├── app/
│   │   ├── core/
│   │   │   ├── auth/             # JWT 攔截器、AuthGuard、登入服務
│   │   │   └── services/         # API 服務（HttpClient 封裝）
│   │   ├── shared/
│   │   │   ├── components/       # 共用元件（metrics-card、result-table 等）
│   │   │   └── pipes/
│   │   └── pages/
│   │       ├── login/            # 登入頁
│   │       ├── home/             # 首頁
│   │       ├── session-overview/ # Session Overview
│   │       ├── loop-detail/      # Loop Detail + 失敗原因分析
│   │       ├── comparison/       # Comparison
│   │       └── import/           # Import Sessions
│   └── environments/
├── angular.json
└── package.json
```

### 頁面對照

| Streamlit 頁面 | Angular 路由 | 主要元件 |
|----------------|-------------|---------|
| Home（app.py） | `/` | `HomeComponent` |
| Session Overview | `/sessions/:id/overview` | `SessionOverviewComponent` |
| Loop Detail | `/sessions/:id/loops/:loop` | `LoopDetailComponent` |
| Comparison | `/sessions/:id/comparison` | `ComparisonComponent` |
| Import Sessions | `/import` | `ImportComponent` |

### 圖表函式庫選擇

現有 Streamlit 使用 Plotly Python，Angular 端建議：

| 圖表類型 | 建議函式庫 | 說明 |
|---------|-----------|------|
| 折線圖（Trend）| **ECharts（ngx-echarts）** | 彈性高，效能好 |
| Donut 圓餅圖 | **ECharts（ngx-echarts）** | 同上 |
| Heatmap（Test ID × Loop）| **ECharts（ngx-echarts）** | 支援大資料量 heatmap |
| 長條圖（Transition Types）| **ECharts（ngx-echarts）** | 同上 |
| 失敗原因 badge | 純 CSS / Angular Material | 不需要圖表函式庫 |

統一用 **ngx-echarts** 可以減少依賴數量，且 ECharts 的 heatmap 效能比 Plotly 好。

### 狀態管理

| 複雜度 | 方案 |
|--------|------|
| 初期（單頁狀態）| Angular Service + RxJS BehaviorSubject |
| 後期（跨頁共享）| NgRx（若狀態邏輯變複雜再導入）|

### Auth 流程

```
登入頁 → POST /api/auth/token
       → 儲存 access_token / refresh_token（localStorage）
       → Angular HTTP Interceptor 自動帶入 Authorization header
       → JWT 到期時自動用 refresh_token 換新
       → 登出時清除 token，導回登入頁
```

所有需要認證的路由加上 `AuthGuard`。

### Phase 2 完成標準

- [ ] 所有頁面功能對應 Streamlit 版本
- [ ] 圖表（折線、Donut、Heatmap、長條）正常顯示
- [ ] JWT 登入 / 登出 / 自動刷新正常
- [ ] 匯入 ZIP / CSV（含進度顯示）
- [ ] 失敗原因分析表格與 badge 正常
- [ ] Admin 功能（查看所有 session、使用者管理）
- [ ] RWD（至少支援 1280px 以上桌面版）

---

## 7. Phase 3 — 正式切換

### 切換前檢查

- [ ] Phase 1 + Phase 2 所有功能驗證完畢
- [ ] 現有 DuckDB 資料已完整遷移至 PostgreSQL
- [ ] 通知現有使用者新版網址（若 port 或路徑有變）
- [ ] Streamlit 版本保留至少 2 週作為備援

### 資料遷移腳本（DuckDB → PostgreSQL）

```python
# scripts/migrate_duckdb_to_pg.py
import duckdb
import django

# 逐表讀出 DuckDB 資料，透過 Django ORM 寫入 PostgreSQL
# sessions → Session.objects.bulk_create()
# results  → Result.objects.bulk_create(batch_size=1000)
# ...
```

### 切換後

- Streamlit container 停止
- `docker-compose.yml` 移除 Streamlit service
- DNS 導向新的 Angular + Django 服務

---

## 8. Docker 部署變更

### 現有（Streamlit）

```yaml
services:
  pcatp-log:    # Streamlit
volumes:
  atp-data:     # DuckDB 檔案
```

### 目標（Angular + Django-Ninja + PostgreSQL）

```yaml
services:
  db:           # PostgreSQL
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: atplog
      POSTGRES_USER: atplog
      POSTGRES_PASSWORD: <secret>
    volumes:
      - pg-data:/var/lib/postgresql/data

  api:          # Django-Ninja
    build: ./atplog_api
    environment:
      DATABASE_URL: postgresql://atplog:<secret>@db:5432/atplog
      SECRET_KEY: <django-secret>
      JWT_SECRET: <jwt-secret>
    depends_on:
      - db
    volumes:
      - ./config:/app/config    # 保留匯入功能的 config

  web:          # Angular（nginx）
    build: ./atplog-web
    ports:
      - "443:443"   # 或 80，前面掛 nginx reverse proxy
    depends_on:
      - api

volumes:
  pg-data:
```

### 平行運行期（Phase 1 完成後、Phase 2 完成前）

```yaml
services:
  pcatp-log:    # Streamlit（繼續運行，port 8501）
  db:           # PostgreSQL
  api:          # Django-Ninja（port 8000，供開發測試）
```

---

## 9. 各功能對照表

| 功能 | Streamlit 實作位置 | Django-Ninja API | Angular 元件 |
|------|-------------------|-----------------|-------------|
| 登入 | `app.py`（streamlit-authenticator）| `POST /api/auth/token` | `LoginComponent` |
| 登出 | sidebar logout button | 前端清除 token | sidebar |
| 匯入 ZIP/CSV | `pages/00_Upload.py` | `POST /api/sessions/import` | `ImportComponent` |
| Session 列表 | `pages/00_Upload.py` + sidebar | `GET /api/sessions` | sidebar + `ImportComponent` |
| 刪除 Session | `pages/00_Upload.py` | `DELETE /api/sessions/{id}` | `ImportComponent` |
| Home 總覽 | `app.py` home_page() | `GET /api/sessions/{id}` | `HomeComponent` |
| Trend 折線圖 | `pages/01_Session_Overview.py` | `GET /api/sessions/{id}/overview` | `SessionOverviewComponent` |
| Result Heatmap | `pages/01_Session_Overview.py` | 同上 | 同上 |
| Loop 結果表格 | `pages/02_Loop_Detail.py` | `GET /api/.../loops/{n}/results` | `LoopDetailComponent` |
| 失敗原因分析 | `pages/02_Loop_Detail.py` | `GET /api/.../loops/{n}/failure-analysis` | `FailureAnalysisComponent` |
| Log Timeline | `pages/02_Loop_Detail.py` | `GET /api/.../loops/{n}/log-entries` | `LogTimelineComponent` |
| Session Comparison | `pages/03_Comparison.py` | `GET /api/sessions/{id}/comparison` | `ComparisonComponent` |
| Loop Comparison | `pages/03_Comparison.py` | 同上（帶 loop_a / loop_b 參數）| 同上 |
| 使用者管理 | `scripts/create_user.py`（CLI）| `GET/POST /api/admin/users` | Admin 頁面 |
| Session 共享 | `config/shares.yaml` | `POST /api/admin/shares` | Admin 頁面 |
