"""
ATP Log Analyzer — Main Entry Point
=====================================
Run with:
    streamlit run app.py
"""
from pathlib import Path

import streamlit as st
import yaml

st.set_page_config(
    page_title="ATP Log Analyzer",
    page_icon=":material/line_axis:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Main content top padding */
    .block-container { padding: 1.5rem !important; }
    /* Sidebar top padding */
    [data-testid="stSidebarContent"] { padding-top: 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
_CONFIG_PATH = Path(__file__).parent / "config" / "users.yaml"

try:
    import streamlit_authenticator as stauth
    with open(_CONFIG_PATH) as f:
        _auth_config = yaml.safe_load(f)

    authenticator = stauth.Authenticate(
        _auth_config["credentials"],
        _auth_config["cookie"]["name"],
        _auth_config["cookie"]["key"],
        _auth_config["cookie"]["expiry_days"],
    )

    if st.session_state.get("authentication_status") is not True:
        # Not authenticated — hide sidebar and show centered login card
        st.markdown("""
        <style>
        section[data-testid="stSidebar"]      { display: none !important; }
        button[data-testid="collapsedControl"] { display: none !important; }
        /* Replace form's "Login" title text with our own (hidden) */
        [data-testid="stForm"] h2,
        [data-testid="stForm"] h3 { display: none !important; }
        /* Remove form card border and padding */
        [data-testid="stForm"] {
            border: none !important;
            padding: 0 !important;
            box-shadow: none !important;
        }
     
        /* Button fills parent width — override fit-content at every layer */
        [data-testid="stForm"] [data-testid="stElementContainer"][width="fit-content"],
        [data-testid="stForm"] [data-testid="stElementContainer"][width="fit-content"] > div,
        [data-testid="stForm"] .stFormSubmitButton,
        [data-testid="stForm"] .stFormSubmitButton button {
            width: 100% !important;
            max-width: none !important;
            box-sizing: border-box !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("<br>" * 3, unsafe_allow_html=True)
        _, center_col, _ = st.columns([1, 0.7, 1])
        with center_col:
            st.markdown(
                "<h2 style='margin-bottom:1.5rem;text-align:center;'>ATP Log Analyzer</h2>",
                unsafe_allow_html=True,
            )
            authenticator.login()
            if st.session_state.get("authentication_status") is False:
                st.error("帳號或密碼錯誤")
        st.stop()

    # Authenticated — expose helpers via session_state
    _username = st.session_state.get("username", "")
    _cred = _auth_config["credentials"]["usernames"].get(_username, {})
    _is_admin = _cred.get("role", "user") == "admin"
    st.session_state["_username"] = _username
    st.session_state["_is_admin"] = _is_admin

    # Sync shares.yaml → session_shares table
    _shares_path = Path(__file__).parent / "config" / "shares.yaml"
    if _shares_path.exists():
        with open(_shares_path) as f:
            _shares_cfg = yaml.safe_load(f) or {}
        from db.database import sync_shares
        sync_shares(_shares_cfg.get("shares", {}))

    # Logout button in sidebar
    authenticator.logout("登出", "sidebar")
    st.sidebar.markdown(
        f"👤 **{st.session_state.get('name', _username)}**"
        + (" `admin`" if _is_admin else "")
    )
    st.sidebar.divider()

except Exception as e:
    # If auth config missing or library not installed, run without auth (dev mode)
    st.warning(f"⚠️ Auth not configured ({e}). Running in dev mode.")
    st.session_state.setdefault("_username", "dev")
    st.session_state.setdefault("_is_admin", True)


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------
def home_page():
    import pandas as pd
    from components.sidebar import render_sidebar
    from components.metrics_card import render_metrics_card, compute_counts
    from utils.helpers import get_loop_numbers

    session_data, _ = render_sidebar(show_loop_selector=False)

    st.title("ATP Log Analyzer")

    if session_data is None:
        st.info("No test sessions found. Please import log files via **Import Sessions**.")
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


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
pg = st.navigation(
    {
        "": [
            st.Page(home_page, title="Home", icon=":material/cottage:", default=True),
        ],
        "Analysis": [
            st.Page("pages/01_Session_Overview.py", title="Session Overview", icon=":material/expand_circle_right:"),
            st.Page("pages/02_Loop_Detail.py",      title="Loop Detail",      icon=":material/expand_circle_right:"),
            st.Page("pages/03_Comparison.py",       title="Comparison",       icon=":material/expand_circle_right:"),
        ],
        "Data": [
            st.Page("pages/00_Upload.py", title="Import Sessions", icon=":material/database_upload:"),
        ],
    }
)
pg.run()
