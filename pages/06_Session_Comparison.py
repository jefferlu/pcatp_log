"""
Page 6 — Session Comparison
=============================
Compare Fail Parameters across multiple sessions.
Summary table: Median + Min~Max range per session per parameter.
Box plot: distribution of values per session for a selected parameter.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

if not st.session_state.get("_username"):
    st.stop()

from components.sidebar import render_sidebar
from db.database import list_sessions, load_fail_values
from utils.chart_theme import light_layout

render_sidebar(show_loop_selector=False)

# ---------------------------------------------------------------------------
# Session selector
# ---------------------------------------------------------------------------
_username = st.session_state.get("_username", "")
_is_admin = st.session_state.get("_is_admin", False)
all_sessions = list_sessions(_username, is_admin=_is_admin)

if not all_sessions:
    st.info("No sessions imported yet.")
    st.stop()

# Group sessions by log_type for easier filtering
_available_types = sorted({s["log_type"] for s in all_sessions if s.get("log_type")})
if len(_available_types) >= 2:
    _type_filter = st.radio(
        "Filter by type", _available_types,
        horizontal=True, key="cmp_type_filter",
    )
    _filtered = [s for s in all_sessions if s.get("log_type") == _type_filter]
else:
    _filtered = all_sessions

session_options = [s["session_id"] for s in _filtered]
selected_sessions = st.multiselect(
    "Select sessions to compare (2 or more)",
    options=session_options,
    default=st.session_state.get("_cmp_sessions", []),
    key="cmp_session_select",
)
st.session_state["_cmp_sessions"] = selected_sessions

if len(selected_sessions) < 2:
    st.info("Select at least 2 sessions to compare.")
    st.stop()

# ---------------------------------------------------------------------------
# Load fail values
# ---------------------------------------------------------------------------
with st.spinner("Loading fail data…"):
    fail_df = load_fail_values(selected_sessions)

if fail_df.empty:
    st.success("No FAIL records found across the selected sessions.")
    st.stop()

# Keep only parameters that appear as FAIL in at least 2 sessions
param_session_counts = (
    fail_df.groupby("param")["session_id"].nunique()
)
multi_session_params = param_session_counts[param_session_counts >= 2].index
if len(multi_session_params) == 0:
    st.info("No parameters with FAIL in 2 or more sessions.")
    # Show single-session fails anyway
    multi_session_params = param_session_counts.index

fail_df = fail_df[fail_df["param"].isin(multi_session_params)]

# ---------------------------------------------------------------------------
# Summary table: Median + Min~Max per session per parameter
# ---------------------------------------------------------------------------
st.subheader("Fail Parameter Summary")
st.caption("Median (bold) and Min ~ Max range across all loops per session.")

# Build pivot: rows = param, cols = session_id, value = "median [min ~ max]"
summary_rows = []
params_sorted = sorted(fail_df["param"].unique())
for param in params_sorted:
    row: dict = {"Parameter": param}
    for sid in selected_sessions:
        vals = fail_df[(fail_df["param"] == param) & (fail_df["session_id"] == sid)]["numeric_value"]
        if vals.empty:
            row[sid] = "—"
        else:
            med = np.median(vals)
            lo  = vals.min()
            hi  = vals.max()
            row[sid] = f"{med:.2f}  [{lo:.2f} ~ {hi:.2f}]"
    summary_rows.append(row)

summary_df = pd.DataFrame(summary_rows)

# Colour cells where all sessions have data (highlight spread)
def _style_summary(df: pd.DataFrame) -> pd.DataFrame:
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    for col in df.columns:
        if col == "Parameter":
            continue
        for i, val in enumerate(df[col]):
            if val != "—":
                styles.at[df.index[i], col] = "background-color: #FFF8E1;"
    return styles

st.dataframe(
    summary_df.style.apply(_style_summary, axis=None),
    hide_index=True,
    width="stretch",
    column_config={
        "Parameter": st.column_config.TextColumn("Parameter", width=200),
        **{sid: st.column_config.TextColumn(sid, width=220) for sid in selected_sessions},
    },
)

st.divider()

# ---------------------------------------------------------------------------
# Box Plot: select a parameter → one box per session
# ---------------------------------------------------------------------------
st.subheader("Value Distribution by Session")

selected_param = st.selectbox(
    "Select parameter",
    options=params_sorted,
    key="cmp_param_select",
)

if selected_param:
    fig = go.Figure()
    for sid in selected_sessions:
        vals = fail_df[(fail_df["param"] == selected_param) & (fail_df["session_id"] == sid)]["numeric_value"]
        if vals.empty:
            continue
        fig.add_trace(go.Box(
            y=vals.tolist(),
            name=sid,
            boxpoints="all",
            jitter=0.3,
            pointpos=0,
            marker=dict(size=6, opacity=0.7),
        ))

    fig.update_layout(**light_layout(
        yaxis=dict(title="Value"),
        xaxis=dict(title="Session"),
        height=420,
        margin=dict(t=20, b=60, l=60, r=20),
    ))

    with st.container(border=True):
        st.plotly_chart(fig, width="stretch")
