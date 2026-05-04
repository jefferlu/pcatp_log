"""
Page 3 — State Transition
===========================
Analyse result stability across all loops of the selected session.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

if not st.session_state.get("_username"):
    st.stop()

from components.sidebar import render_sidebar
from utils.helpers import get_loop_numbers
from utils.chart_theme import light_layout

session_data, _ = render_sidebar(show_loop_selector=False)

if session_data is None:
    st.info("No session selected. Please import log files via **Import Sessions** and select a session from the sidebar.")
    st.stop()

loops     = session_data.get("loops", {})
loop_nums = get_loop_numbers(session_data)

if len(loop_nums) < 2:
    st.warning("Need at least 2 loops to compare.")
    st.stop()

# ---------------------------------------------------------------------------
# Computation
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
# Session Info
# ---------------------------------------------------------------------------
if not all_results:
    st.info("No result data available.")
    st.stop()

_sess_id    = session_data.get("id", "—")
_log_type   = st.session_state.get("_session_log_type", "") or "—"
_test_mode  = session_data.get("header_meta", {}).get("Test Mode", "") or "—"
_total_loops = len(loop_nums)

st.markdown("""
<style>
[data-testid="stMetricLabel"] { font-size: 0.7rem !important; }
[data-testid="stMetricValue"] { font-size: 1.1rem !important; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Session",     _sess_id)
    c2.metric("Type",        _log_type)
    c3.metric("Test Mode",   _test_mode)
    c4.metric("Total Loops", _total_loops)

st.divider()

if transition_df.empty:
    st.success("No state transitions detected across all loops.")
    st.stop()

# ---------------------------------------------------------------------------
# Transition Types chart + Unstable Items table
# ---------------------------------------------------------------------------
type_counts: dict[str, int] = {}
for _, row in transition_df.iterrows():
    for segment in row["Detail"].split("  |  "):
        if ": " in segment:
            t = segment.split(": ", 1)[1]
            type_counts[t] = type_counts.get(t, 0) + 1

CARD_HEIGHT = 400
col_chart, col_table = st.columns([1, 2])

with col_chart:
    st.subheader("Transition Types")
    with st.container(border=True):
        labels = list(type_counts.keys())
        values = list(type_counts.values())
        color_map = {
            "PASS→FAIL":  "#EE3333",
            "FAIL→PASS":  "#00AA55",
            "PASS→BLOCK": "#DD8800",
            "BLOCK→PASS": "#00AA55",
            "FAIL→BLOCK": "#DD8800",
            "BLOCK→FAIL": "#EE3333",
        }
        colors = [color_map.get(l, "#AAAAAA") for l in labels]
        fig_bar = go.Figure(go.Bar(
            x=labels, y=values,
            marker_color=colors,
            text=values, textposition="outside",
        ))
        fig_bar.update_layout(**light_layout(
            yaxis=dict(title="Count"),
            margin=dict(t=10, b=40, l=20, r=20),
            height=CARD_HEIGHT,
        ))
        st.plotly_chart(fig_bar, width="stretch")

with col_table:
    st.subheader(f"Unstable Items (Top {min(20, len(transition_df))})")
    st.dataframe(
        transition_df.head(20)[["Test ID", "Category", "Test Name", "Sub Item", "Transitions", "Detail"]],
        width="stretch",
        hide_index=True,
        height=CARD_HEIGHT + 32,
    )

st.divider()

# ---------------------------------------------------------------------------
# Result Sequence per Unstable Item
# ---------------------------------------------------------------------------
st.subheader("Result Sequence per Unstable Item")
top_ids = transition_df.head(30)["Test ID"].tolist()
selected_id = st.selectbox(
    "Select Test ID to inspect",
    top_ids,
    format_func=lambda tid: (
        f"{tid} — {ref_info[tid]['Test Name']} / {ref_info[tid]['Sub Item']}"
    ),
)
if selected_id:
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
            height=300,
        ))
        st.plotly_chart(fig_seq, width="stretch")
