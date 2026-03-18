"""
ATP Log Analyzer — Main Entry Point
=====================================
Run with:
    streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="ATP Log Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Main content top padding */
    .block-container { padding-top: 1.5rem !important; }
    /* Sidebar top padding */
    [data-testid="stSidebarContent"] { padding-top: 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def home_page():
    import pandas as pd
    from components.sidebar import render_sidebar
    from components.metrics_card import render_metrics_card, compute_counts
    from utils.helpers import get_loop_numbers

    session_data, _ = render_sidebar(show_loop_selector=False)

    st.title("ATP Log Analyzer")
    st.markdown(
        "Event-after reconstruction of ATP system real-time test screens from log files."
    )

    if session_data is None:
        st.warning("No test sessions found. Please check the `.log_files/` directory.")
        st.stop()

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
                "✅ Pass":   counts["passed"],
                "❌ Fail":   counts["failed"],
                "🚫 Block":  counts["blocked"],
            })

        summary_df = pd.DataFrame(rows)
        st.dataframe(summary_df, width="stretch", hide_index=True)
    else:
        st.warning("No loop data found in this session.")


pg = st.navigation(
    {
        "": [
            st.Page(home_page, title="Home", icon="📔", default=True),
        ],
        "Analysis": [
            st.Page("pages/01_Session_Overview.py", title="Session Overview", icon="📔"),
            st.Page("pages/02_Loop_Detail.py",      title="Loop Detail",      icon="📔"),
            st.Page("pages/03_Comparison.py",       title="Comparison",       icon="📔"),
        ],
        "Data": [
            st.Page("pages/00_Upload.py", title="Import Sessions", icon="📔"),
        ],
    }
)
pg.run()
