"""
Generate ATP Log Analyzer user manual as PDF.
Usage: python scripts/generate_manual.py
Output: ATP_Log_Analyzer_Manual.pdf
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Font registration (Arial Unicode — supports CJK, TTF format)
# ---------------------------------------------------------------------------
FONT_PATH = "/Library/Fonts/Arial Unicode.ttf"
pdfmetrics.registerFont(TTFont("PingFang",      FONT_PATH))
pdfmetrics.registerFont(TTFont("PingFang-Bold", FONT_PATH))
pdfmetrics.registerFontFamily("PingFang", normal="PingFang", bold="PingFang-Bold")

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
BLUE       = colors.HexColor("#00AAFF")
DARK       = colors.HexColor("#1A1A2E")
LIGHT_GREY = colors.HexColor("#F4F6F8")
MID_GREY   = colors.HexColor("#CCCCCC")
GREEN      = colors.HexColor("#00AA55")
RED        = colors.HexColor("#EE3333")
AMBER      = colors.HexColor("#DD8800")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def make_styles():
    s = getSampleStyleSheet()
    base = dict(fontName="PingFang", leading=18)

    cover_title = ParagraphStyle("CoverTitle",
        fontName="PingFang-Bold", fontSize=28, alignment=TA_CENTER,
        textColor=DARK, spaceAfter=10, leading=36)

    cover_sub = ParagraphStyle("CoverSub",
        fontName="PingFang", fontSize=14, alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"), spaceAfter=6, leading=20)

    h1 = ParagraphStyle("H1",
        fontName="PingFang-Bold", fontSize=18, textColor=BLUE,
        spaceBefore=20, spaceAfter=8, leading=24)

    h2 = ParagraphStyle("H2",
        fontName="PingFang-Bold", fontSize=13, textColor=DARK,
        spaceBefore=14, spaceAfter=6, leading=18)

    body = ParagraphStyle("Body",
        fontName="PingFang", fontSize=10.5, textColor=colors.HexColor("#333333"),
        spaceBefore=4, spaceAfter=4, leading=17)

    note = ParagraphStyle("Note",
        fontName="PingFang", fontSize=9.5, textColor=colors.HexColor("#666666"),
        spaceBefore=2, spaceAfter=2, leading=15,
        leftIndent=12, borderPad=4)

    code = ParagraphStyle("Code",
        fontName="Courier", fontSize=9, textColor=colors.HexColor("#222222"),
        backColor=LIGHT_GREY, spaceBefore=4, spaceAfter=4,
        leftIndent=10, leading=14)

    toc_entry = ParagraphStyle("TocEntry",
        fontName="PingFang", fontSize=10.5, leading=20,
        textColor=DARK, spaceAfter=2)

    return dict(cover_title=cover_title, cover_sub=cover_sub,
                h1=h1, h2=h2, body=body, note=note, code=code,
                toc_entry=toc_entry)

ST = make_styles()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def H1(text): return Paragraph(text, ST["h1"])
def H2(text): return Paragraph(text, ST["h2"])
def P(text):  return Paragraph(text, ST["body"])
def Note(text): return Paragraph(f"📌 {text}", ST["note"])
def Code(text): return Paragraph(text, ST["code"])
def SP(n=0.3): return Spacer(1, n * cm)
def HR(): return HRFlowable(width="100%", thickness=0.5, color=MID_GREY, spaceAfter=6)

def bullet_list(items: list[str]):
    return ListFlowable(
        [ListItem(P(i), leftIndent=20, bulletColor=BLUE) for i in items],
        bulletType="bullet", bulletFontName="PingFang",
        leftIndent=12, spaceBefore=4, spaceAfter=4,
    )

def table(data, col_widths=None, header=True):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("FONTNAME",    (0, 0), (-1, -1), "PingFang"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9.5),
        ("LEADING",     (0, 0), (-1, -1), 15),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
        ("GRID",        (0, 0), (-1, -1), 0.4, MID_GREY),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]
    if header:
        style += [
            ("BACKGROUND",  (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "PingFang-Bold"),
        ]
    t.setStyle(TableStyle(style))
    return t

# ---------------------------------------------------------------------------
# Content builder
# ---------------------------------------------------------------------------
def build_content() -> list:
    story = []

    # ── Cover ────────────────────────────────────────────────────────────────
    story += [
        SP(4),
        Paragraph("ATP Log Analyzer", ST["cover_title"]),
        Paragraph("使用者操作手冊", ST["cover_sub"]),
        SP(0.5),
        HRFlowable(width="60%", thickness=2, color=BLUE, hAlign="CENTER"),
        SP(0.5),
        Paragraph("User Operation Manual", ST["cover_sub"]),
        SP(1),
        Paragraph("版本 1.0 ｜ 2026", ST["cover_sub"]),
        PageBreak(),
    ]

    # ── 1. 系統概述 ──────────────────────────────────────────────────────────
    story += [H1("1. 系統概述"), HR()]
    story += [P(
        "ATP Log Analyzer 是一套本機單機運行的測試記錄分析工具，"
        "專為 ATP（Automated Test Program）系統產生的 CSV 與 TXT log 檔案設計。"
        "透過 DuckDB 資料庫儲存測試結果，並以互動式網頁介面呈現各 loop 的 "
        "PASS / FAIL / BLOCK 狀態及跨 loop 的穩定性分析。"
    )]
    story += [SP(), H2("1.1 主要功能")]
    story += [bullet_list([
        "匯入 ZIP 或 CSV 格式的 ATP log 檔案至本機資料庫",
        "Session Overview：趨勢折線圖、Donut 圓餅圖、Result Heatmap",
        "Loop Detail：測試結果表格（含篩選）、即時 Log Timeline",
        "Comparison：兩 Loop 比較、Session 狀態翻轉分析、整體穩定性統計",
        "單機 Windows 執行檔，無需安裝 Python",
    ])]
    story += [SP(), H2("1.2 系統需求")]
    story += [table(
        [["項目", "規格"],
         ["作業系統", "Windows 10/11（執行檔）/ macOS（開發模式）"],
         ["瀏覽器", "Chrome、Edge、Firefox（任一現代瀏覽器）"],
         ["記憶體", "建議 4GB 以上"],
         ["儲存空間", "執行檔約 400MB，資料庫另計"],
         ["網路", "不需要（完全離線運行）"]],
        col_widths=[5*cm, 11*cm],
    )]
    story += [PageBreak()]

    # ── 2. 啟動應用程式 ──────────────────────────────────────────────────────
    story += [H1("2. 啟動應用程式"), HR()]
    story += [H2("2.1 Windows 執行檔（一般使用者）")]
    story += [bullet_list([
        "將 <b>ATPLogAnalyzer</b> 資料夾複製到任意位置",
        "雙擊 <b>ATPLogAnalyzer.exe</b>",
        "系統自動在瀏覽器開啟 <b>http://localhost:&lt;port&gt;</b>",
        "資料庫檔案 <b>atp_log.duckdb</b> 儲存在同一資料夾，關閉後資料保留",
    ])]
    story += [Note("首次啟動約需 5–10 秒，請等候瀏覽器自動開啟。")]
    story += [SP(), H2("2.2 開發模式（macOS / 命令列）")]
    story += [Code("cd /path/to/pcatp_log")]
    story += [Code("streamlit run app.py")]
    story += [PageBreak()]

    # ── 3. 匯入資料 ──────────────────────────────────────────────────────────
    story += [H1("3. 匯入資料（Import Sessions）"), HR()]
    story += [P("在側邊欄點選 <b>Import Sessions</b> 進入匯入頁面。")]
    story += [SP(), H2("3.1 支援格式")]
    story += [table(
        [["格式", "說明"],
         ["ZIP", "將整個 session 資料夾壓縮成 zip，可包含多個 session"],
         ["CSV（多選）", "直接選取同一 session 的所有 .csv 檔案"]],
        col_widths=[4*cm, 12*cm],
    )]
    story += [SP(), H2("3.2 ATP Log 檔案結構")]
    story += [P("每個 session 資料夾包含以下成對檔案：")]
    story += [table(
        [["檔案", "說明"],
         ["Session 總表 .csv", "不含 loop 編號的 CSV，為測點清單（無結果欄位）"],
         ["Loop 結果 .csv", "Loop N 的最終測試結果（PASS/FAIL/BLOCK），header 含 Test Loop 欄位"],
         ["Log .txt", "Loop N 的即時執行 Log（與 Loop 結果 CSV 成對）"]],
        col_widths=[5*cm, 11*cm],
    )]
    story += [Note(
        "系統以 CSV 檔案的 header 內容（是否含 Test Loop 欄位）判斷檔案類型，"
        "不限制檔案命名格式，支援 EMM、IMM 等各種測試模式。"
        "CSV 為測試完成後的最終判定，TXT 為執行過程的即時記錄（含 retry），兩者獨立產生。"
    )]
    story += [SP(), H2("3.3 匯入步驟")]
    story += [bullet_list([
        "點選 <b>Upload Log Files</b> 區塊中的「Choose file(s)」",
        "選取 ZIP 或多個 CSV 檔案",
        "確認 <b>Overwrite if session already exists</b>（預設勾選）",
        "點擊 <b>Import</b> 按鈕，等候進度條完成",
        "成功後出現綠色提示，session 自動加入側邊欄選單",
    ])]
    story += [SP(), H2("3.4 已匯入 Session 管理")]
    story += [bullet_list([
        "頁面下方 <b>Imported Sessions</b> 列出所有已匯入的 session",
        "顯示：Session ID、Test Mode、Loop 數量、匯入時間",
        "點擊 <b>Delete</b> 可刪除該 session 的所有資料",
    ])]
    story += [PageBreak()]

    # ── 4. 側邊欄操作 ────────────────────────────────────────────────────────
    story += [H1("4. 側邊欄操作"), HR()]
    story += [P("所有分析頁面共用同一側邊欄，包含以下元素：")]
    story += [table(
        [["元素", "說明"],
         ["Test Session", "下拉選單，選擇要分析的 session（依匯入時間排序）"],
         ["Loop", "下拉選單（僅 Loop Detail 頁出現），選擇單一 loop 查看詳情"],
         ["Session info", "顯示 Session ID、已載入 loop 數、Test Mode"]],
        col_widths=[4*cm, 12*cm],
    )]
    story += [Note("切換 Session 後，所有頁面自動更新為新 session 的資料。")]
    story += [PageBreak()]

    # ── 5. Home ──────────────────────────────────────────────────────────────
    story += [H1("5. 首頁（Home）"), HR()]
    story += [P("提供目前選取 session 的總覽資訊。")]
    story += [SP(), H2("5.1 Session 基本資訊")]
    story += [bullet_list([
        "Session ID：唯一識別碼",
        "Test Mode：測試模式（如 EMM、IMM 等）",
        "Total Loops：本 session 共有幾個 loop",
    ])]
    story += [SP(), H2("5.2 Aggregate Summary")]
    story += [P("彙總所有 loop 的 PASS / FAIL / BLOCK / Total 計數。")]
    story += [SP(), H2("5.3 Per-Loop Summary 表格")]
    story += [P(
        "列出每個 loop 的結束時間、測試總數及 PASS / FAIL / BLOCK 數量，"
        "方便快速比較各 loop 的整體表現。"
    )]
    story += [PageBreak()]

    # ── 6. Session Overview ──────────────────────────────────────────────────
    story += [H1("6. Session Overview"), HR()]
    story += [P("以圖表形式呈現整個 session 的測試趨勢與分布。")]
    story += [SP(), H2("6.1 Pass / Fail / Block Trend")]
    story += [P(
        "折線圖顯示每個 loop 的 PASS（綠）/ FAIL（紅）/ BLOCK（橙）數量變化，"
        "可快速識別哪個 loop 發生異常。"
    )]
    story += [SP(), H2("6.2 Loop Breakdown（Donut 圓餅圖）")]
    story += [P("以首個 loop 為例，顯示 PASS / FAIL / BLOCK 的比例分布。")]
    story += [SP(), H2("6.3 Result Heatmap")]
    story += [P(
        "X 軸為 Loop 編號，Y 軸為 Test ID，顏色代表該測點在各 loop 的結果："
    )]
    story += [table(
        [["顏色", "結果"],
         ["🟢 綠色", "PASS"],
         ["🔴 紅色", "FAIL"],
         ["🟠 橙色", "BLOCK"]],
        col_widths=[4*cm, 12*cm],
    )]
    story += [P("可快速識別哪些測點在多個 loop 中持續失敗（整列紅色）。")]
    story += [PageBreak()]

    # ── 7. Loop Detail ───────────────────────────────────────────────────────
    story += [H1("7. Loop Detail"), HR()]
    story += [P("查看單一 loop 的詳細測試結果與執行 log。先在側邊欄選擇 Loop 編號。")]
    story += [SP(), H2("7.1 Summary Metrics")]
    story += [P("顯示該 loop 的 Total / Passed / Failed / Blocked 計數及百分比。")]
    story += [SP(), H2("7.2 Test Results 表格")]
    story += [P("列出所有測點的詳細結果，支援兩種篩選器：")]
    story += [table(
        [["篩選器", "說明"],
         ["Category", "依測試類別篩選（如 CAN Error、Interlock Feedback）"],
         ["Result", "依結果篩選（PASS / FAIL / BLOCK / 全部）"]],
        col_widths=[4*cm, 12*cm],
    )]
    story += [SP(), H2("7.3 Log Timeline")]
    story += [P("顯示該 loop 的即時執行記錄，支援以 Log Level 篩選：")]
    story += [table(
        [["Level", "說明"],
         ["fail", "失敗事件（紅色）"],
         ["error", "系統錯誤（橙色）"],
         ["warning", "警告訊息（黃色）"],
         ["pass", "通過事件（綠色）"],
         ["info", "一般資訊（灰色）"]],
        col_widths=[3*cm, 13*cm],
    )]
    story += [PageBreak()]

    # ── 8. Comparison ────────────────────────────────────────────────────────
    story += [H1("8. Comparison"), HR()]
    story += [P("提供兩個視角的跨 loop 比較分析，以頁籤切換。")]

    story += [SP(), H2("8.1 Session Comparison（Session 內翻轉分析）")]
    story += [P("分析整個 session 中每個測點的完整狀態變化軌跡：")]
    story += [bullet_list([
        "<b>Summary Metrics</b>：總測點數、不穩定測點數、翻轉總次數",
        "<b>Transition Types</b> 長條圖：各類翻轉（PASS→FAIL 等）的次數分布",
        "<b>Unstable Items</b> 表格：翻轉最頻繁的測點排行，含詳細軌跡",
        "<b>Result Sequence</b>：選取單一測點，查看其在所有 loop 的狀態走勢折線圖",
    ])]
    story += [Note(
        "狀態翻轉以每個 loop 的 CSV 最終結果為準（已包含 retry 後的判定），"
        "不會將 retry 過程中的 FAIL 視為翻轉。"
    )]

    story += [SP(), H2("8.2 Loop Comparison（兩 Loop 比較）")]
    story += [bullet_list([
        "從下拉選單分別選取 <b>Loop A</b> 和 <b>Loop B</b>",
        "系統自動比對兩 loop 間結果有差異的測點，列為 <b>Changed Items</b>",
        "未變動的測點收折在 Expander 中",
    ])]
    story += [PageBreak()]

    # ── 9. 常見問題 ──────────────────────────────────────────────────────────
    story += [H1("9. 常見問題（FAQ）"), HR()]
    story += [table(
        [["問題", "解決方式"],
         ["No sessions in database", "前往 Import Sessions 頁面先匯入 log 檔案"],
         ["No loop data found", "確認上傳的 session 資料夾中有 loop 結果 CSV（header 含 Test Loop 欄位）"],
         ["Log Timeline 顯示空白", "該 loop 無對應的 _TestSetResponse.txt 檔案（正常現象）"],
         ["Heatmap 顯示 Not enough data", "該 session 只有 1 個 loop，無法繪製跨 loop 熱圖"],
         ["State Transition Analysis 無資料", "該 session 所有測點在所有 loop 中結果完全一致"],
         ["EXE 啟動後瀏覽器未開啟", "等待約 10 秒，或手動開啟 http://localhost:8501"]],
        col_widths=[6*cm, 10*cm],
    )]
    story += [SP(0.5)]

    return story


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    out_path = Path(__file__).parent.parent / "ATP_Log_Analyzer_Manual.pdf"

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2.5*cm,
        topMargin=2.5*cm,  bottomMargin=2.5*cm,
        title="ATP Log Analyzer 使用者操作手冊",
        author="ATP Log Analyzer",
    )

    doc.build(build_content())
    print(f"✅  Manual generated: {out_path}")


if __name__ == "__main__":
    main()
