"""
Page 2 — Loop Detail
======================
Reproduces the ATP real-time screen for a single selected loop.
Shows categorised test results, value gauges, and the raw log timeline.
"""
import pandas as pd
import streamlit as st

if not st.session_state.get("_username"):
    st.stop()

from components.sidebar import render_sidebar
from components.metrics_card import render_metrics_card, compute_counts
from components.result_table import (
    render_result_table,
    render_category_filter,
    render_result_filter,
)
from utils.helpers import get_loop_numbers, LOG_LEVEL_COLORS
from utils.failure_analysis import analyze_failures, ROOT_CAUSE_COLOR, ROOT_CAUSE_ICON

session_data, selected_loop = render_sidebar(show_loop_selector=True)


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
# Value gauge chart for range-type items (disabled)
# ---------------------------------------------------------------------------
# st.subheader("Measurement Values vs. Limits")
#
# gauge_rows = []
# if not results_df.empty and "Value" in results_df.columns:
#     for _, row in results_df.iterrows():
#         parsed = format_value_cell(str(row.get("Value", "")))
#         if parsed["type"] == "range":
#             gauge_rows.append({
#                 "name":   f"{row.get('Test Name','')} / {row.get('Sub Item','')}",
#                 "result": str(row.get("Result", "")).strip().upper(),
#                 "min":    parsed["min"],
#                 "max":    parsed["max"],
#                 "lo":     parsed["lo"],
#                 "hi":     parsed["hi"],
#             })
#
# if gauge_rows:
#     with st.container(border=True):
#         fig = go.Figure()
#         for i, g in enumerate(gauge_rows):
#             color = "#00AA55" if g["result"] == "PASS" else (
#                 "#EE3333" if g["result"] == "FAIL" else "#DD8800"
#             )
#             fig.add_trace(go.Bar(
#                 x=[(g["max"] + g["min"]) / 2],
#                 y=[g["name"]],
#                 orientation="h",
#                 width=max(g["max"] - g["min"], 1),
#                 base=g["min"],
#                 marker_color=color,
#                 name=g["result"],
#                 showlegend=(i == 0),
#                 hovertemplate=(
#                     f"<b>{g['name']}</b><br>"
#                     f"Measured: {g['min']:.1f} ~ {g['max']:.1f}<br>"
#                     f"Limit: {g['lo']:.1f} ~ {g['hi']:.1f}<br>"
#                     f"Result: {g['result']}<extra></extra>"
#                 ),
#             ))
#             for limit_val in [g["lo"], g["hi"]]:
#                 fig.add_shape(
#                     type="line",
#                     x0=limit_val, x1=limit_val,
#                     y0=i - 0.4, y1=i + 0.4,
#                     line=dict(color="#444444", width=1, dash="dot"),
#                 )
#
#         fig.update_layout(**light_layout(
#             height=max(400, len(gauge_rows) * 22),
#             barmode="overlay",
#             yaxis=dict(autorange="reversed"),
#             showlegend=False,
#             margin=dict(l=250),
#         ))
#         st.plotly_chart(fig, width="stretch")
# else:
#     st.info("No range-type measurement data available for this loop.")

# ---------------------------------------------------------------------------
# Failure Analysis
# ---------------------------------------------------------------------------
from db.database import load_log_entries
log_entries = load_log_entries(session_data["id"], selected_loop)

st.divider()
st.subheader("Failure Analysis")

fail_df = analyze_failures(results_df, log_entries)

if fail_df.empty:
    st.success("No failures to analyse in this loop.")
else:
    # Summary badges
    cause_counts = fail_df["Root Cause"].value_counts()
    badge_cols = st.columns(min(len(cause_counts), 5))
    for i, (cause, cnt) in enumerate(cause_counts.items()):
        color = ROOT_CAUSE_COLOR.get(cause, "#999999")
        icon  = ROOT_CAUSE_ICON.get(cause, "?")
        badge_cols[i % len(badge_cols)].markdown(
            f"<div style='background:{color}22;border-left:4px solid {color};"
            f"padding:0.4rem 0.8rem;border-radius:4px;margin-bottom:0.4rem'>"
            f"<span style='color:{color};font-weight:600'>{icon} {cause}</span>"
            f"<span style='float:right;font-weight:700;color:{color}'>{cnt}</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("")

    # Detail table
    display_df = fail_df.copy()
    st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Test ID":      st.column_config.NumberColumn("Monitor ID", width=80),
            "Category":     st.column_config.TextColumn("Category",   width=160),
            "Test Name":    st.column_config.TextColumn("Test Name",  width=130),
            "Sub Item":     st.column_config.TextColumn("Sub Item",   width=180),
            "Root Cause":   st.column_config.TextColumn("Root Cause", width=170),
            "Actual":       st.column_config.TextColumn("Actual",     width=180),
            "Limit":        st.column_config.TextColumn("Limit",      width=180),
            "Deviation":    st.column_config.TextColumn("Dev",        width=70),
            "Log Evidence": st.column_config.TextColumn("Log Evidence"),
        },
    )

# ---------------------------------------------------------------------------
# Log timeline
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Log Timeline")

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
