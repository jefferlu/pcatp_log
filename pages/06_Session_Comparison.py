"""
Page 6 — Fail Distribution
============================
Select one or more sessions to view each session's fail parameter
distribution across loops, and export the data to Excel.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from openpyxl.styles import PatternFill, Font

if not st.session_state.get("_username"):
    st.stop()

from components.sidebar import render_sidebar
from db.database import list_sessions, load_fail_values

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
    "Select session(s)",
    options=session_options,
    default=[s for s in st.session_state.get("_cmp_sessions", []) if s in session_options],
    key="cmp_session_select",
)
st.session_state["_cmp_sessions"] = selected_sessions

if not selected_sessions:
    st.info("Select at least one session.")
    st.stop()

# ---------------------------------------------------------------------------
# Load fail values
# ---------------------------------------------------------------------------
with st.spinner("Loading fail data…"):
    fail_df = load_fail_values(selected_sessions)

if fail_df.empty:
    st.success("No FAIL records with numeric values found.")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# Per-session sections
# ---------------------------------------------------------------------------
for session_id in selected_sessions:
    sess_df = fail_df[fail_df["session_id"] == session_id]
    if sess_df.empty:
        st.warning(f"**{session_id}** — no numeric fail values.")
        continue

    params_sorted = sorted(sess_df["param"].unique())

    with st.expander(f"**{session_id}** — {len(params_sorted)} fail parameter(s)", expanded=True):
        # Summary table
        summary_rows = []
        for param in params_sorted:
            vals = sess_df[sess_df["param"] == param]["numeric_value"]
            loop_count = sess_df[sess_df["param"] == param]["loop_num"].nunique()
            summary_rows.append({
                "Parameter":  param,
                "Total Fail Loops": int(loop_count),
                "Median":     round(float(np.median(vals)), 4),
                "Min":        round(float(vals.min()), 4),
                "Max":        round(float(vals.max()), 4),
                "Range":      round(float(vals.max() - vals.min()), 4),
            })
        summary_df = pd.DataFrame(summary_rows)

        st.dataframe(
            summary_df,
            hide_index=True,
            width="stretch",
            column_config={
                "Parameter":  st.column_config.TextColumn("Parameter",    width=220),
                "Total Fail Loops": st.column_config.NumberColumn("Total Fail Loops", width=90),
                "Median":     st.column_config.NumberColumn("Median",     width=100, format="%.4f"),
                "Min":        st.column_config.NumberColumn("Min",        width=100, format="%.4f"),
                "Max":        st.column_config.NumberColumn("Max",        width=100, format="%.4f"),
                "Range":      st.column_config.NumberColumn("Range",      width=100, format="%.4f"),
            },
        )

        # Box plot
        plottable = [p for p in params_sorted if len(sess_df[sess_df["param"] == p]) >= 2]
        if plottable:
            fig = go.Figure()
            for param in plottable:
                pdata = sess_df[sess_df["param"] == param]
                fig.add_trace(go.Box(
                    y=pdata["numeric_value"].tolist(),
                    name=param,
                    text=[f"Loop {l}" for l in pdata["loop_num"].tolist()],
                    boxpoints="all",
                    jitter=0.3,
                    pointpos=0,
                    marker=dict(size=6, opacity=0.7),
                    hovertemplate="%{text}<br>Value: %{y}<extra></extra>",
                ))
            fig.update_layout(
                height=max(380, 55 * len(plottable)),
                margin=dict(t=20, b=120, l=60, r=20),
                xaxis=dict(tickangle=-35),
                yaxis=dict(title="Value"),
                showlegend=False,
            )
            with st.container(border=True):
                st.plotly_chart(fig, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
# Excel export — one sheet per session
# ---------------------------------------------------------------------------
st.subheader("Export to Excel")

def _build_excel(sessions: list[str], df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for session_id in sessions:
            sess_df = df[df["session_id"] == session_id]
            if sess_df.empty:
                continue

            # Summary
            summary_rows = []
            for param in sorted(sess_df["param"].unique()):
                vals = sess_df[sess_df["param"] == param]["numeric_value"]
                summary_rows.append({
                    "Parameter":  param,
                    "Total Fail Loops": int(vals.count()),
                    "Median":     round(float(np.median(vals)), 4),
                    "Min":        round(float(vals.min()), 4),
                    "Max":        round(float(vals.max()), 4),
                    "Range":      round(float(vals.max() - vals.min()), 4),
                })
            summary_df = pd.DataFrame(summary_rows)

            # Raw
            raw_df = sess_df[["loop_num", "test_name", "sub_item", "param", "numeric_value"]].copy()
            raw_df.columns = ["Loop", "Test Name", "Sub Item", "Parameter", "Value"]
            raw_df = raw_df.sort_values(["Parameter", "Loop"])

            # Write to single sheet: summary at top, blank row, then raw
            sheet_name = session_id[:31]
            summary_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=0)
            raw_start = len(summary_df) + 2  # +1 header, +1 blank row
            raw_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=raw_start)

            # Apply header background colours
            ws = writer.sheets[sheet_name]
            _sum_fill = PatternFill("solid", fgColor="4472C4")  # blue
            _raw_fill = PatternFill("solid", fgColor="70AD47")  # green
            _font     = Font(color="FFFFFF", bold=True)
            for cell in ws[1]:                          # summary header row (row 1)
                if cell.value is not None:
                    cell.fill = _sum_fill
                    cell.font = _font
            for cell in ws[raw_start + 1]:              # raw header row
                if cell.value is not None:
                    cell.fill = _raw_fill
                    cell.font = _font

            # Auto-fit column widths
            for col in ws.columns:
                max_len = max(
                    (len(str(cell.value)) for cell in col if cell.value is not None),
                    default=8,
                )
                ws.column_dimensions[col[0].column_letter].width = max_len + 2

    buf.seek(0)
    return buf.read()

fname = "fail_distribution.xlsx"
with st.spinner("Building Excel…"):
    excel_bytes = _build_excel(selected_sessions, fail_df)
st.download_button(
    label="Download Excel",
    data=excel_bytes,
    file_name=fname,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)
