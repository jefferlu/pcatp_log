"""
Page 3 — Comparison
=====================
Compare results across multiple loops or sessions.
(Phase 1 skeleton — full implementation in Phase 4)
"""
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Comparison", page_icon="⚖️", layout="wide")

from components.sidebar import render_sidebar, _cached_load_session
from utils.helpers import discover_sessions, get_loop_numbers

session_data, _ = render_sidebar(show_loop_selector=False)

st.title("⚖️ Comparison")
st.info(
    "**Phase 1 skeleton** — Full multi-loop and cross-session comparison "
    "will be implemented in Phase 4."
)

if session_data is None:
    st.stop()

loops = session_data.get("loops", {})
loop_nums = get_loop_numbers(session_data)

if len(loop_nums) < 2:
    st.warning("Need at least 2 loops to compare.")
    st.stop()

# ---------------------------------------------------------------------------
# Simple two-loop comparison
# ---------------------------------------------------------------------------
st.subheader("Two-Loop Comparison")

col1, col2 = st.columns(2)
with col1:
    loop_a = st.selectbox("Loop A", loop_nums, index=0, key="cmp_loop_a",
                          format_func=lambda n: f"Loop {n}")
with col2:
    loop_b = st.selectbox("Loop B", loop_nums,
                          index=min(1, len(loop_nums) - 1), key="cmp_loop_b",
                          format_func=lambda n: f"Loop {n}")

if loop_a == loop_b:
    st.warning("Please select two different loops.")
    st.stop()

df_a = loops[loop_a].get("results", pd.DataFrame())
df_b = loops[loop_b].get("results", pd.DataFrame())

if df_a.empty or df_b.empty:
    st.warning("One or both selected loops have no result data.")
    st.stop()

# Merge on Test ID
merged = df_a[["Test ID", "Category", "Test Name", "Sub Item", "Result"]].rename(
    columns={"Result": f"Result_L{loop_a}"}
).merge(
    df_b[["Test ID", "Result"]].rename(columns={"Result": f"Result_L{loop_b}"}),
    on="Test ID",
    how="outer",
)

# Highlight rows where result changed
def _mark_change(row):
    a = str(row.get(f"Result_L{loop_a}", "")).strip().upper()
    b = str(row.get(f"Result_L{loop_b}", "")).strip().upper()
    return a != b

merged["Changed"] = merged.apply(_mark_change, axis=1)

changed_df = merged[merged["Changed"]].drop(columns=["Changed"])
same_df    = merged[~merged["Changed"]].drop(columns=["Changed"])

st.markdown(f"**{len(changed_df)}** items changed result between Loop {loop_a} and Loop {loop_b}.")

if not changed_df.empty:
    st.subheader("Changed Items")
    st.dataframe(changed_df, width="stretch", hide_index=True)

with st.expander(f"Unchanged items ({len(same_df)})", expanded=False):
    st.dataframe(same_df, width="stretch", hide_index=True)
