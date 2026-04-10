"""
Page 1 — Session Overview
===========================
Shows aggregate summary, per-loop PASS/FAIL/BLOCK trends and test-item heatmap.
"""
import pandas as pd
import plotly.express as px  # used for pie chart
import plotly.graph_objects as go
import streamlit as st

if not st.session_state.get("_username"):
    st.stop()

from components.sidebar import render_sidebar
from components.metrics_card import render_metrics_card, compute_counts
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
# Per-loop stats for charts
# ---------------------------------------------------------------------------
chart_rows = []
for ln in loop_nums:
    counts = compute_counts(loops[ln].get("results"))
    chart_rows.append({"Loop": ln, **counts})
stats_df = pd.DataFrame(chart_rows)

# ---------------------------------------------------------------------------
# Trend line chart
# ---------------------------------------------------------------------------
st.subheader("Pass / Fail / Block Trend per Loop")
with st.container(border=True):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=stats_df["Loop"], y=stats_df["passed"],
        mode="lines+markers", name="PASS",
        line=dict(color="#00AA55", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=stats_df["Loop"], y=stats_df["failed"],
        mode="lines+markers", name="FAIL",
        line=dict(color="#EE3333", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=stats_df["Loop"], y=stats_df["blocked"],
        mode="lines+markers", name="BLOCK",
        line=dict(color="#DD8800", width=2),
    ))
    fig.update_layout(**light_layout(
        xaxis=dict(title="Loop"),
        yaxis=dict(title="Count"),
    ))
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Overall donut chart for first loop with data
# ---------------------------------------------------------------------------
first_loop = loop_nums[0]
first_counts = compute_counts(loops[first_loop].get("results"))

col_breakdown, col_seq = st.columns([1, 2])

with col_breakdown:
    st.subheader(f"Loop {first_loop} Breakdown")
    with st.container(border=True):
        fig_pie = px.pie(
            names=["PASS", "FAIL", "BLOCK"],
            values=[first_counts["passed"], first_counts["failed"], first_counts["blocked"]],
            color=["PASS", "FAIL", "BLOCK"],
            color_discrete_map={"PASS": "#00AA55", "FAIL": "#EE3333", "BLOCK": "#DD8800"},
            hole=0.45,
        )
        fig_pie.update_layout(**light_layout())
        st.plotly_chart(fig_pie, width="stretch")

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
    sequence = [(ln, loop_map[ln]) for ln in loop_nums if ln in loop_map]
    flips = []
    for i in range(1, len(sequence)):
        prev_loop, prev_res = sequence[i - 1]
        curr_loop, curr_res = sequence[i]
        if prev_res in VALID and curr_res in VALID and prev_res != curr_res:
            flips.append(f"L{prev_loop}→L{curr_loop}: {prev_res}→{curr_res}")
    if flips:
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
# Result Sequence per Unstable Item
# ---------------------------------------------------------------------------
with col_seq:
    st.subheader("Result Sequence per Unstable Item")
    if transition_df.empty:
        st.success("No state transitions detected across all loops.")
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
