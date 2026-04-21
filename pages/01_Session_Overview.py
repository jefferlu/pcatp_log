"""
Page 1 — Session Overview
===========================
Shows aggregate summary, per-loop PASS/FAIL/BLOCK trends and test-item heatmap.
"""
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

if not st.session_state.get("_username"):
    st.stop()

from components.sidebar import render_sidebar
from components.metrics_card import render_metrics_card, compute_counts
from db.database import get_spec_mapping
from utils.helpers import get_loop_numbers
from utils.chart_theme import light_layout

session_data, _ = render_sidebar(show_loop_selector=False)

if session_data is None:
    st.info("No session selected. Please import log files via **Import Sessions** and select a session from the sidebar.")
    st.stop()

loops = session_data.get("loops", {})
loop_nums = get_loop_numbers(session_data)

if not loop_nums:
    st.warning("No loop data found.")
    st.stop()

# ---------------------------------------------------------------------------
# Aggregate Summary (All Loops)
# ---------------------------------------------------------------------------
total_p = total_f = total_b = total_t = 0
for ln in loop_nums:
    counts = compute_counts(loops[ln].get("results"))
    total_p += counts["passed"]
    total_f += counts["failed"]
    total_b += counts["blocked"]
    total_t += counts["total"]

render_metrics_card(total=total_t, passed=total_p, failed=total_f, blocked=total_b, title="")

# st.divider()

# ---------------------------------------------------------------------------
# Per-Loop Summary table
# ---------------------------------------------------------------------------
st.subheader("Per-Loop Summary")
rows = []
for ln in loop_nums:
    ldata = loops[ln]
    hdr = ldata.get("header", {})
    counts = compute_counts(ldata.get("results"))
    rows.append({
        "Loop":     ln,
        "End Time": hdr.get("Test End Time", "—"),
        "Total":    counts["total"],
        "Pass":   counts["passed"],
        "Fail":   counts["failed"],
        "Block":  counts["blocked"],
    })
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Fail Parameters across all loops
# ---------------------------------------------------------------------------
_RANGE_RE    = re.compile(r"Min:([\d.Ee+\-]+)\s+Max:([\d.Ee+\-]+)\s*\|\s*Limit\[([\d.Ee+\-]+)~([\d.Ee+\-]+)\]")
_AVG_RE      = re.compile(r"Avg:([\d.Ee+\-]+)\s*\|\s*Limit\[([\d.Ee+\-]+)~([\d.Ee+\-]+)\]")

fail_rows = []
for ln in loop_nums:
    df = loops[ln].get("results", pd.DataFrame())
    if df.empty:
        continue
    fail_df = df[df["Result"].str.strip().str.upper() == "FAIL"]
    for _, row in fail_df.iterrows():
        val = str(row.get("Value", "")).strip()
        m = _RANGE_RE.search(val)
        if m:
            fail_rows.append({
                "Loop":      ln,
                "Test Name": row.get("Test Name", ""),
                "Sub Item":  row.get("Sub Item", ""),
                "Min":       float(m.group(1)),
                "Max":       float(m.group(2)),
                "Limit Lo":  float(m.group(3)),
                "Limit Hi":  float(m.group(4)),
            })
            continue
        m = _AVG_RE.search(val)
        if m:
            fail_rows.append({
                "Loop":      ln,
                "Test Name": row.get("Test Name", ""),
                "Sub Item":  row.get("Sub Item", ""),
                "Min":       float(m.group(1)),
                "Max":       float(m.group(1)),
                "Limit Lo":  float(m.group(2)),
                "Limit Hi":  float(m.group(3)),
            })

if fail_rows:
    st.subheader("Fail Parameters")
    fail_table = pd.DataFrame(fail_rows)

    # Join spec mapping (pin_no, evo_imm_group) by test_name and session log_type
    _log_type = st.session_state.get("_session_log_type", "")
    try:
        if _log_type:
            _spec = get_spec_mapping(_log_type)[["test_name", "pin_no", "evo_imm_group"]]
            _spec = _spec.rename(columns={
                "test_name":     "Test Name",
                "pin_no":        "Pin No",
                "evo_imm_group": "EVO IMM Group",
            })
            fail_table = fail_table.merge(_spec, on="Test Name", how="left")
    except Exception:
        _log_type = ""  # skip spec columns if table not ready

    # Assign alternating color index per loop group
    _loop_order = list(dict.fromkeys(fail_table["Loop"]))
    _loop_color = {ln: i % 2 for i, ln in enumerate(_loop_order)}
    _BG = ["#F8F8F8", "#EEF4FF"]  # light grey / light blue

    _loop_per_row = [_BG[_loop_color[ln]] for ln in fail_table["Loop"]]

    def _style_fail_table(df: pd.DataFrame) -> pd.DataFrame:
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for i, idx in enumerate(df.index):
            styles.loc[idx] = f"background-color: {_loop_per_row[i]}"
        return styles

    _col_config = {
        "Loop":      st.column_config.NumberColumn("Loop",     width=60),
        "Test Name": st.column_config.TextColumn("Test Name", width=160),
        "Sub Item":  st.column_config.TextColumn("Sub Item",  width=180),
        "Min":       st.column_config.NumberColumn("Min",      width=90, format="%.2f"),
        "Max":       st.column_config.NumberColumn("Max",      width=90, format="%.2f"),
        "Limit Lo":  st.column_config.NumberColumn("Limit Lo", width=90, format="%.2f"),
        "Limit Hi":  st.column_config.NumberColumn("Limit Hi", width=90, format="%.2f"),
    }
    if _log_type:
        _col_config["Pin No"]        = st.column_config.TextColumn("Pin No",        width=120)
        _col_config["EVO IMM Group"] = st.column_config.TextColumn("EVO IMM Group", width=120)

    st.dataframe(
        fail_table.style.apply(_style_fail_table, axis=None),
        width="stretch",
        hide_index=True,
        column_config=_col_config,
    )
    st.divider()

# ---------------------------------------------------------------------------
# Transition computation
# ---------------------------------------------------------------------------
VALID = {"PASS", "FAIL", "BLOCK"}
all_results: dict[str, dict[int, str]] = {}
ref_info:    dict[str, dict]           = {}

for ln in loop_nums:
    df = loops[ln].get("results", pd.DataFrame())
    if df.empty or "Test ID" not in df.columns:
        continue
    for _, row in df.iterrows():
        tid = str(row.get("Test ID", ""))
        res = str(row.get("Result", "")).strip().upper()
        if tid not in all_results:
            all_results[tid] = {}
            ref_info[tid] = {
                "Category":  row.get("Category", ""),
                "Test Name": row.get("Test Name", ""),
                "Sub Item":  row.get("Sub Item", ""),
            }
        all_results[tid][ln] = res

transition_rows: list[dict] = []
for tid, loop_map in all_results.items():
    has_fail = any(r == "FAIL" for r in loop_map.values())
    if not has_fail:
        continue
    sequence = [(ln, loop_map[ln]) for ln in loop_nums if ln in loop_map]
    flips = []
    for i in range(1, len(sequence)):
        prev_loop, prev_res = sequence[i - 1]
        curr_loop, curr_res = sequence[i]
        if prev_res in VALID and curr_res in VALID and prev_res != curr_res:
            flips.append(f"L{prev_loop}→L{curr_loop}: {prev_res}→{curr_res}")
    transition_rows.append({
        "Test ID":     tid,
        "Category":    ref_info[tid]["Category"],
        "Test Name":   ref_info[tid]["Test Name"],
        "Sub Item":    ref_info[tid]["Sub Item"],
        "Transitions": len(flips),
        "Detail":      "  |  ".join(flips),
    })

transition_df = (
    pd.DataFrame(transition_rows).sort_values("Transitions", ascending=False)
    if transition_rows else pd.DataFrame()
)

# ---------------------------------------------------------------------------
# Result Sequence per Fail Item
# ---------------------------------------------------------------------------
st.subheader("Result Sequence per Fail Item")
if transition_df.empty:
    st.success("No failures detected across all loops.")
else:
    top_ids = transition_df.head(30)["Test ID"].tolist()
    selected_id = st.selectbox(
        "Select Test ID to inspect",
        top_ids,
        format_func=lambda tid: (
            f"{tid} — {ref_info[tid]['Test Name']} / {ref_info[tid]['Sub Item']}"
        ),
    )
    if selected_id:
        _test_name = ref_info[selected_id]["Test Name"]
        seq_data = [
            {"Loop": ln, "Result": all_results[selected_id].get(ln, "N/A")}
            for ln in loop_nums
            if ln in all_results[selected_id]
        ]
        seq_df = pd.DataFrame(seq_data)
        result_num = {"PASS": 1, "BLOCK": 0, "FAIL": -1}
        seq_df["Value"] = seq_df["Result"].map(lambda r: result_num.get(r, None))

        with st.container(border=True):
            fig_seq = go.Figure()
            fig_seq.add_trace(go.Scatter(
                x=seq_df["Loop"],
                y=seq_df["Value"],
                mode="lines+markers+text",
                text=seq_df["Result"],
                textposition="top center",
                hovertemplate=f"{_test_name}<extra></extra>",
                marker=dict(
                    size=10,
                    color=seq_df["Result"].map({
                        "PASS": "#00AA55", "FAIL": "#EE3333",
                        "BLOCK": "#DD8800", "N/A": "#AAAAAA",
                    }),
                ),
                line=dict(color="#AAAAAA", width=1, dash="dot"),
            ))
            fig_seq.update_layout(**light_layout(
                yaxis=dict(
                    tickvals=[-1, 0, 1],
                    ticktext=["FAIL", "BLOCK", "PASS"],
                    range=[-1.5, 1.5],
                    title="",
                ),
                xaxis=dict(title="Loop", dtick=1),
                height=365,
            ))
            st.plotly_chart(fig_seq, width="stretch")
