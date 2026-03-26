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
    .block-container { padding-top: 1rem !important; }
    /* Sidebar top padding */
    [data-testid="stSidebarContent"] { padding-top: 0 !important; }
    /* Logout button — hyperlink style */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:last-child button,
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button {
        background: none !important;
        border: none !important;
        box-shadow: none !important;
        padding: 2px 0 !important;
        line-height: 1.4 !important;
        font-size: 0.875rem !important;
        text-decoration: underline !important;
        color: inherit !important;
        cursor: pointer !important;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:last-child button:hover,
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button:hover {
        background: none !important;
        color: var(--primary-color) !important;
    }
</style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
_CONFIG_PATH = Path(__file__).parent / "config" / "users.yaml"

@st.cache_resource
def _load_auth_config():
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

try:
    import streamlit_authenticator as stauth  # type: ignore[import-untyped]
    _auth_config = _load_auth_config()
    authenticator = stauth.Authenticate(
        _auth_config["credentials"],
        _auth_config["cookie"]["name"],
        _auth_config["cookie"]["key"],
        _auth_config["cookie"]["expiry_days"],
    )

    if st.session_state.get("authentication_status") is not True:
        # Render form-specific CSS (does not affect sidebar/page transition timing)
        st.markdown("""
        <style>
        /* Hide "Press Enter to submit form" hint on input focus */
        [data-testid="InputInstructions"],
        small[data-testid="InputInstructions"],
        .stTextInput small { display: none !important; visibility: hidden !important; }
        /* Center the form title rendered by streamlit-authenticator */
        [data-testid="stForm"] h2,
        [data-testid="stForm"] h3 { text-align: center !important; }
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
            authenticator.login(fields={
                'Form name': 'ATP Log Analyzer',
                'Username': 'Username',
                'Password': 'Password',
                'Login': 'Login',
            })
            if st.session_state.get("authentication_status") is False:
                st.error("Invalid username or password")

        # Hide sidebar last — injected just before render completes so sidebar
        # disappears together with page content, not before.
        st.markdown("""
        <style>
        section[data-testid="stSidebar"]      { display: none !important; }
        button[data-testid="collapsedControl"] { display: none !important; }
        </style>
        """, unsafe_allow_html=True)
        st.stop()

    # Authenticated — expose helpers via session_state
    _username = st.session_state.get("username", "")
    _cred = _auth_config["credentials"]["usernames"].get(_username, {})
    _is_admin = _cred.get("role", "user") == "admin"
    st.session_state["_username"] = _username
    st.session_state["_is_admin"] = _is_admin

    # Sidebar: username (left) + logout button (right) on same row
    _col_name, _col_out = st.sidebar.columns([3, 1])
    _col_name.markdown(
        f":material/account_circle: *{st.session_state.get('name', _username)}*"
        + (" `admin`" if _is_admin else "")
    )
    with _col_out:
        authenticator.logout("Logout", location="main", key="logout_btn")


except Exception as e:
    # If auth config missing or library not installed, run without auth (dev mode)
    st.warning(f"⚠️ Auth not configured ({e}). Running in dev mode.")
    st.session_state.setdefault("_username", "dev")
    st.session_state.setdefault("_is_admin", True)
    authenticator = None


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
pg = st.navigation(
    {
        "Analysis": [
            st.Page("pages/01_Session_Overview.py", title="Session Overview", icon=":material/expand_circle_right:", default=True),
            st.Page("pages/02_Loop_Detail.py",      title="Loop Detail",      icon=":material/expand_circle_right:"),
            st.Page("pages/03_Comparison.py",       title="Comparison",       icon=":material/expand_circle_right:"),
        ],
        "Data": [
            st.Page("pages/00_Upload.py", title="Import Sessions", icon=":material/database_upload:"),
        ],
    }
)
pg.run()
