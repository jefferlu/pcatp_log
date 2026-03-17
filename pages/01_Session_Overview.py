"""
Page 1 — Session Overview
===========================
Shows per-loop PASS/FAIL/BLOCK trends and test-item heatmap.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Session Overview", page_icon="📊", layout="wide")

from components.sidebar import render_sidebar
from components.metrics_card import render_metrics_card, compute_counts
from utils.helpers import get_loop_numbers

session_data, _ = render_sidebar(show_loop_selector=False)

st.title("📊 Session Overview")

if session_data is None:
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
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=stats_df["Loop"], y=stats_df["passed"],
    mode="lines+markers", name="PASS",
    line=dict(color="#00CC66", width=2),
))
fig.add_trace(go.Scatter(
    x=stats_df["Loop"], y=stats_df["failed"],
    mode="lines+markers", name="FAIL",
    line=dict(color="#FF4444", width=2),
))
fig.add_trace(go.Scatter(
    x=stats_df["Loop"], y=stats_df["blocked"],
    mode="lines+markers", name="BLOCK",
    line=dict(color="#FFAA00", width=2),
))
fig.update_layout(
    xaxis_title="Loop",
    yaxis_title="Count",
    plot_bgcolor="#1C2333",
    paper_bgcolor="#0E1117",
    font_color="#FAFAFA",
    legend=dict(bgcolor="#1C2333"),
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Overall donut chart for first loop with data
# ---------------------------------------------------------------------------
first_loop = loop_nums[0]
first_counts = compute_counts(loops[first_loop].get("results"))

col_donut, col_stats = st.columns([1, 2])
with col_donut:
    st.subheader(f"Loop {first_loop} Breakdown")
    fig_pie = px.pie(
        names=["PASS", "FAIL", "BLOCK"],
        values=[first_counts["passed"], first_counts["failed"], first_counts["blocked"]],
        color=["PASS", "FAIL", "BLOCK"],
        color_discrete_map={"PASS": "#00CC66", "FAIL": "#FF4444", "BLOCK": "#FFAA00"},
        hole=0.45,
    )
    fig_pie.update_layout(
        paper_bgcolor="#0E1117", font_color="#FAFAFA",
        legend=dict(bgcolor="#1C2333"),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

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

    fig_heat = px.imshow(
        heat_df,
        color_continuous_scale=[
            [0.0,  "#FF4444"],   # FAIL = -1
            [0.5,  "#FFAA00"],   # BLOCK = 0
            [1.0,  "#00CC66"],   # PASS = 1
        ],
        zmin=-1, zmax=1,
        aspect="auto",
        labels=dict(x="Loop", y="Test ID", color="Result"),
    )
    fig_heat.update_layout(
        paper_bgcolor="#0E1117",
        plot_bgcolor="#1C2333",
        font_color="#FAFAFA",
        coloraxis_showscale=False,
        height=max(400, len(all_ids) * 8),
    )
    st.plotly_chart(fig_heat, use_container_width=True)
else:
    st.info("Not enough data for heatmap.")
