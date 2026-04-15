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
from db.database import list_sessions, load_fail_values, load_all_results

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
            pdata = sess_df[sess_df["param"] == param]
            vals = pdata["numeric_value"]
            loop_count = pdata["loop_num"].nunique()
            lmin = pdata["limit_min"].dropna().iloc[0] if pdata["limit_min"].notna().any() else None
            lmax = pdata["limit_max"].dropna().iloc[0] if pdata["limit_max"].notna().any() else None
            summary_rows.append({
                "Parameter":        param,
                "Total Fail Loops": int(loop_count),
                "Limit Min":        round(float(lmin), 4) if lmin is not None else None,
                "Limit Max":        round(float(lmax), 4) if lmax is not None else None,
                "Val Min":          round(float(vals.min()), 4),
                "Val Max":          round(float(vals.max()), 4),
                "Median":           round(float(np.median(vals)), 4),
                "Range":            round(float(vals.max() - vals.min()), 4),
            })
        summary_df = pd.DataFrame(summary_rows)

        def _style_summary(df: pd.DataFrame) -> pd.DataFrame:
            styles = pd.DataFrame("", index=df.index, columns=df.columns)
            _fail_bg = "background-color: #FFCCCC;"
            _out_bg  = "background-color: #FF6666; font-weight: bold;"
            for i, row in df.iterrows():
                # Highlight Val Min red if below Limit Min
                if pd.notna(row.get("Limit Min")) and pd.notna(row.get("Val Min")):
                    if row["Val Min"] < row["Limit Min"]:
                        styles.at[i, "Val Min"] = _out_bg
                # Highlight Val Max red if above Limit Max
                if pd.notna(row.get("Limit Max")) and pd.notna(row.get("Val Max")):
                    if row["Val Max"] > row["Limit Max"]:
                        styles.at[i, "Val Max"] = _out_bg
                # Light red on entire row for fail parameters
                for col in df.columns:
                    if styles.at[i, col] == "":
                        styles.at[i, col] = _fail_bg
            return styles

        st.dataframe(
            summary_df.style.apply(_style_summary, axis=None),
            hide_index=True,
            width="stretch",
            column_config={
                "Parameter":        st.column_config.TextColumn("Parameter",         width=220),
                "Total Fail Loops": st.column_config.NumberColumn("Total Fail Loops", width=100),
                "Limit Min":        st.column_config.NumberColumn("Limit Min",        width=100, format="%.4f"),
                "Limit Max":        st.column_config.NumberColumn("Limit Max",        width=100, format="%.4f"),
                "Val Min":          st.column_config.NumberColumn("Val Min",          width=100, format="%.4f"),
                "Val Max":          st.column_config.NumberColumn("Val Max",          width=100, format="%.4f"),
                "Median":           st.column_config.NumberColumn("Median",           width=100, format="%.4f"),
                "Range":            st.column_config.NumberColumn("Range",            width=100, format="%.4f"),
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

_total_loops_map = {s["session_id"]: s["total_loops"] for s in all_sessions}

with st.spinner("Loading all results for export…"):
    all_results_df = load_all_results(selected_sessions)

def _build_excel(sessions: list[str], fail_df: pd.DataFrame, all_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    _sum_fill  = PatternFill("solid", fgColor="4472C4")   # blue — summary header
    _raw_fill  = PatternFill("solid", fgColor="70AD47")   # green — raw header
    _fail_fill = PatternFill("solid", fgColor="FFCCCC")   # red — fail rows
    _hdr_font  = Font(color="FFFFFF", bold=True)

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for session_id in sessions:
            sess_fail = fail_df[fail_df["session_id"] == session_id]
            sess_all  = all_df[all_df["session_id"] == session_id]
            if sess_all.empty:
                continue

            total_loops = _total_loops_map.get(session_id, "—")

            # Summary (from fail data)
            summary_rows = []
            for param in sorted(sess_fail["param"].unique()) if not sess_fail.empty else []:
                pdata = sess_fail[sess_fail["param"] == param]
                vals  = pdata["numeric_value"]
                lmin  = pdata["limit_min"].dropna().iloc[0] if pdata["limit_min"].notna().any() else None
                lmax  = pdata["limit_max"].dropna().iloc[0] if pdata["limit_max"].notna().any() else None
                summary_rows.append({
                    "Parameter":        param,
                    "Total Fail Loops": int(vals.count()),
                    "Total Loops":      total_loops,
                    "Limit Min":        round(float(lmin), 4) if lmin is not None else "",
                    "Limit Max":        round(float(lmax), 4) if lmax is not None else "",
                    "Val Min":          round(float(vals.min()), 4),
                    "Val Max":          round(float(vals.max()), 4),
                    "Median":           round(float(np.median(vals)), 4),
                    "Range":            round(float(vals.max() - vals.min()), 4),
                })
            summary_df = pd.DataFrame(summary_rows)

            # Raw — all parameters, sorted by loop then test_name
            raw_df = sess_all[["loop_num", "test_name", "sub_item", "result", "value"]].copy()
            raw_df.columns = ["Loop", "Test Name", "Sub Item", "Result", "Value"]
            raw_df = raw_df.sort_values(["Loop", "Test Name", "Sub Item"]).reset_index(drop=True)

            # Write sheets
            sheet_name = session_id[:31]
            summary_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=0)
            raw_start = len(summary_df) + 2
            raw_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=raw_start)

            ws = writer.sheets[sheet_name]

            # Header colours
            for cell in ws[1]:
                if cell.value is not None:
                    cell.fill = _sum_fill
                    cell.font = _hdr_font
            for cell in ws[raw_start + 1]:
                if cell.value is not None:
                    cell.fill = _raw_fill
                    cell.font = _hdr_font

            # Highlight FAIL rows in raw table
            result_col_idx = raw_df.columns.get_loc("Result") + 1  # 1-based
            for row_offset, result_val in enumerate(raw_df["Result"]):
                if str(result_val).upper() == "FAIL":
                    excel_row = raw_start + 2 + row_offset  # +2: header row + 1-based
                    for cell in ws[excel_row]:
                        if cell.column <= len(raw_df.columns):
                            cell.fill = _fail_fill

            # Auto-fit column widths
            for col in ws.columns:
                max_len = max(
                    (len(str(cell.value)) for cell in col if cell.value is not None),
                    default=8,
                )
                ws.column_dimensions[col[0].column_letter].width = max_len + 2

    buf.seek(0)
    return buf.read()

fname = "Fail_Distribution.xlsx"
with st.spinner("Building Excel…"):
    excel_bytes = _build_excel(selected_sessions, fail_df, all_results_df)
st.download_button(
    label="Download Excel",
    data=excel_bytes,
    file_name=fname,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)
