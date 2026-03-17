"""
Page 2 — Loop Detail
======================
Reproduces the ATP real-time screen for a single selected loop.
Shows categorised test results, value gauges, and the raw log timeline.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Loop Detail", page_icon="🔍", layout="wide")

from components.sidebar import render_sidebar
from components.metrics_card import render_metrics_card, compute_counts
from components.result_table import (
    render_result_table,
    render_category_filter,
    render_result_filter,
)
from parsers.log_parser import parse_test_set_response
from utils.helpers import get_loop_numbers, LOG_LEVEL_COLORS, format_value_cell

session_data, selected_loop = render_sidebar(show_loop_selector=True)

st.title("🔍 Loop Detail")

if session_data is None or selected_loop is None:
    st.info("Select a session and loop from the sidebar.")
    st.stop()

loops = session_data.get("loops", {})
if selected_loop not in loops:
    st.warning(f"Loop {selected_loop} not found.")
    st.stop()

loop_data = loops[selected_loop]
results_df = loop_data.get("results", pd.DataFrame())
legacy_df  = loop_data.get("legacy",  pd.DataFrame())
header     = loop_data.get("header",  {})

# ---------------------------------------------------------------------------
# Header info
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Loop", selected_loop)
with col2:
    st.metric("End Time", header.get("Test End Time", "—"))
with col3:
    st.metric("Mode", header.get("Test Mode", "—"))

st.divider()

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------
counts = compute_counts(results_df)
render_metrics_card(**counts)

st.divider()

# ---------------------------------------------------------------------------
# Result Table (with filters)
# ---------------------------------------------------------------------------
st.subheader("Test Results")
fcol1, fcol2 = st.columns(2)
with fcol1:
    cat_filter = render_category_filter(results_df, key=f"cat_{selected_loop}")
with fcol2:
    res_filter = render_result_filter(key=f"res_{selected_loop}")

render_result_table(
    results_df,
    filter_category=cat_filter,
    filter_result=res_filter,
    key=f"tbl_{selected_loop}",
)

# ---------------------------------------------------------------------------
# Legacy rows (CAN / LIN)
# ---------------------------------------------------------------------------
if not legacy_df.empty:
    with st.expander("Legacy Rows (CAN / LIN / etc.)", expanded=False):
        render_result_table(
            legacy_df,
            show_value=True,
            height=300,
            key=f"legacy_{selected_loop}",
        )

st.divider()

# ---------------------------------------------------------------------------
# Value gauge chart for range-type items
# ---------------------------------------------------------------------------
st.subheader("Measurement Values vs. Limits")

gauge_rows = []
if not results_df.empty and "Value" in results_df.columns:
    for _, row in results_df.iterrows():
        parsed = format_value_cell(str(row.get("Value", "")))
        if parsed["type"] == "range":
            gauge_rows.append({
                "name":   f"{row.get('Test Name','')} / {row.get('Sub Item','')}",
                "result": str(row.get("Result", "")).strip().upper(),
                "min":    parsed["min"],
                "max":    parsed["max"],
                "lo":     parsed["lo"],
                "hi":     parsed["hi"],
            })

if gauge_rows:
    fig = go.Figure()
    for i, g in enumerate(gauge_rows):
        color = "#00CC66" if g["result"] == "PASS" else (
            "#FF4444" if g["result"] == "FAIL" else "#FFAA00"
        )
        # Bar for measured range
        fig.add_trace(go.Bar(
            x=[(g["max"] + g["min"]) / 2],
            y=[g["name"]],
            orientation="h",
            width=max(g["max"] - g["min"], 1),
            base=g["min"],
            marker_color=color,
            name=g["result"],
            showlegend=(i == 0),
            hovertemplate=(
                f"<b>{g['name']}</b><br>"
                f"Measured: {g['min']:.1f} ~ {g['max']:.1f}<br>"
                f"Limit: {g['lo']:.1f} ~ {g['hi']:.1f}<br>"
                f"Result: {g['result']}<extra></extra>"
            ),
        ))
        # Limit lines
        for limit_val in [g["lo"], g["hi"]]:
            fig.add_shape(
                type="line",
                x0=limit_val, x1=limit_val,
                y0=i - 0.4, y1=i + 0.4,
                line=dict(color="#FFFFFF", width=1, dash="dot"),
            )

    fig.update_layout(
        height=max(400, len(gauge_rows) * 22),
        barmode="overlay",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#1C2333",
        font_color="#FAFAFA",
        yaxis=dict(autorange="reversed"),
        showlegend=False,
        margin=dict(l=250),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No range-type measurement data available for this loop.")

# ---------------------------------------------------------------------------
# Log timeline
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Log Timeline")

session_id = session_data["id"]
loop_num_str = str(selected_loop)
from pathlib import Path
from utils.helpers import LOG_ROOT

log_path = LOG_ROOT / session_id / f"{loop_num_str}_EMM_{session_id}_TestSetResponse.txt"
log_entries = parse_test_set_response(log_path)

if log_entries:
    level_filter = st.multiselect(
        "Show log levels",
        options=["info", "pass", "fail", "error", "warning"],
        default=["fail", "error", "warning", "pass"],
        key=f"logfilter_{selected_loop}",
    )
    filtered_entries = [e for e in log_entries if e["level"] in level_filter]

    log_html = '<div style="font-family:monospace;font-size:0.82em;max-height:500px;overflow-y:auto">'
    for e in filtered_entries:
        color = LOG_LEVEL_COLORS.get(e["level"], "#AAAAAA")
        time_part = f'<span style="color:#888">[{e["time"]}]</span> ' if e["time"] else ""
        mod_part  = (f'<span style="color:#00AAFF">[{e["module"]}]</span> '
                     if e["module"] not in ("raw", "") else "")
        msg_part  = f'<span style="color:{color}">{e["message"]}</span>'
        log_html += f"<div>{time_part}{mod_part}{msg_part}</div>"
    log_html += "</div>"
    st.markdown(log_html, unsafe_allow_html=True)
else:
    st.info("Log file not found or empty.")
