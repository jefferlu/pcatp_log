"""
ATP Log Analyzer — Main Entry Point
=====================================
Run with:
    streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="ATP Log Analyzer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

from components.sidebar import render_sidebar
from components.metrics_card import render_metrics_card, compute_counts
from utils.helpers import get_loop_numbers

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
session_data, selected_loop = render_sidebar(show_loop_selector=False)

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.title("🔬 ATP Log Analyzer")
st.markdown(
    "Event-after reconstruction of ATP system real-time test screens from log files."
)

if session_data is None:
    st.warning("No test sessions found. Please check the `.log_files/` directory.")
    st.stop()

# --- Session header info ---
meta = session_data.get("header_meta", {})
loops = session_data.get("loops", {})
loop_nums = get_loop_numbers(session_data)

col_info1, col_info2, col_info3 = st.columns(3)
with col_info1:
    st.info(f"**Session ID**\n\n`{session_data['id']}`")
with col_info2:
    st.info(f"**Test Mode**\n\n`{meta.get('Test Mode', '—')}`")
with col_info3:
    st.info(f"**Total Loops**\n\n`{len(loop_nums)}`")

st.divider()

# --- Aggregate stats across all loops ---
if loop_nums:
    st.subheader("Aggregate Summary (All Loops)")

    total_p = total_f = total_b = total_t = 0
    for ln in loop_nums:
        ldata = loops[ln]
        counts = compute_counts(ldata.get("results"))
        total_p += counts["passed"]
        total_f += counts["failed"]
        total_b += counts["blocked"]
        total_t += counts["total"]

    render_metrics_card(
        total=total_t,
        passed=total_p,
        failed=total_f,
        blocked=total_b,
        title="",
    )

    st.divider()

    # --- Per-loop summary table ---
    st.subheader("Per-Loop Summary")
    rows = []
    for ln in loop_nums:
        ldata = loops[ln]
        hdr = ldata.get("header", {})
        counts = compute_counts(ldata.get("results"))
        rows.append({
            "Loop":    ln,
            "End Time": hdr.get("Test End Time", "—"),
            "Total":   counts["total"],
            "✅ Pass":  counts["passed"],
            "❌ Fail":  counts["failed"],
            "🚫 Block": counts["blocked"],
        })

    import pandas as pd
    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(
        "👈 Use the **sidebar** to navigate to detailed pages, "
        "or select from the pages menu."
    )
else:
    st.warning("No loop data found in this session.")
