"""
Page 1 — Session Overview
===========================
Shows per-loop PASS/FAIL/BLOCK trends and test-item heatmap.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

if not st.session_state.get("_username"):
    st.stop()

from components.sidebar import render_sidebar
from components.metrics_card import render_metrics_card, compute_counts
from utils.helpers import get_loop_numbers
from utils.chart_theme import light_layout

session_data, _ = render_sidebar(show_loop_selector=False)

st.title("Session Overview")

if session_data is None:
    st.info("No session selected. Please import log files via **Import Sessions** and select a session from the sidebar.")
    st.stop()

loops = session_data.get("loops", {})
loop_nums = get_loop_numbers(session_data)

if not loop_nums:
    st.warning("No loop data found.")
    st.stop()

# ---------------------------------------------------------------------------
# Per-loop stats table
# ---------------------------------------------------------------------------
rows = []
for ln in loop_nums:
    counts = compute_counts(loops[ln].get("results"))
    rows.append({"Loop": ln, **counts})
stats_df = pd.DataFrame(rows)

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

col_donut, col_stats = st.columns([1, 2])
with col_donut:
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

with col_stats:
    render_metrics_card(
        total=first_counts["total"],
        passed=first_counts["passed"],
        failed=first_counts["failed"],
        blocked=first_counts["blocked"],
        title=f"Loop {first_loop} Summary",
    )

# ---------------------------------------------------------------------------
# Heatmap: Result per Test ID × Loop
# ---------------------------------------------------------------------------
st.subheader("Result Heatmap (Test ID × Loop)")

result_map = {"PASS": 1, "FAIL": -1, "BLOCK": 0, "": None}
heatmap_data = {}
all_ids: list[int] = []

for ln in loop_nums:
    df = loops[ln].get("results", pd.DataFrame())
    if df.empty or "Test ID" not in df.columns:
        continue
    for _, row in df.iterrows():
        tid = row.get("Test ID")
        res = str(row.get("Result", "")).strip().upper()
        if tid not in heatmap_data:
            heatmap_data[tid] = {}
        heatmap_data[tid][ln] = result_map.get(res, None)
    all_ids = sorted(set(all_ids) | set(df["Test ID"].tolist()))

if heatmap_data and all_ids:
    heat_df = pd.DataFrame(heatmap_data, index=loop_nums).T  # Test ID × Loop
    heat_df = heat_df.loc[sorted(heat_df.index)]

    with st.container(border=True):
        fig_heat = px.imshow(
            heat_df,
            color_continuous_scale=[
                [0.0,  "#EE3333"],   # FAIL = -1
                [0.5,  "#DD8800"],   # BLOCK = 0
                [1.0,  "#00AA55"],   # PASS = 1
            ],
            zmin=-1, zmax=1,
            aspect="auto",
            labels=dict(x="Loop", y="Test ID", color="Result"),
        )
        fig_heat.update_layout(**light_layout(
            coloraxis_showscale=False,
            height=max(400, len(all_ids) * 8),
        ))
        st.plotly_chart(fig_heat, width="stretch")
else:
    st.info("Not enough data for heatmap.")
