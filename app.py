"""
ATP Log Analyzer — Main Entry Point
=====================================
Run with:
    streamlit run app.py
"""
from pathlib import Path

import bcrypt
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


def _reload_auth_config():
    """Clear the cache and reload users.yaml. Call after any write to users.yaml."""
    _load_auth_config.clear()
    return _load_auth_config()


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
        /* Delay login tabs appearance to prevent flash during cookie validation */
        [data-testid="stTabs"] {
            animation: fadeInTabs 0s ease 0.3s both;
        }
        @keyframes fadeInTabs {
            from { opacity: 0; }
            to   { opacity: 1; }
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("<br>" * 3, unsafe_allow_html=True)
        _, center_col, _ = st.columns([1, 0.7, 1])
        with center_col:
            tab_login, tab_register = st.tabs(["Login", "Register"])

            with tab_login:
                authenticator.login(fields={
                    'Form name': 'ATP Log Analyzer',
                    'Username': 'Username',
                    'Password': 'Password',
                    'Login': 'Login',
                })
                if st.session_state.get("authentication_status") is False:
                    st.error("Invalid username or password")

            with tab_register:
                with st.form("register_form"):
                    st.markdown("### Create Account")
                    reg_username    = st.text_input("Username")
                    reg_name        = st.text_input("Display Name")
                    reg_email       = st.text_input("Email")
                    reg_password    = st.text_input("Password",         type="password")
                    reg_confirm     = st.text_input("Confirm Password", type="password")
                    submitted = st.form_submit_button("Register", use_container_width=True)

                if submitted:
                    _cfg = _load_auth_config()
                    _users = _cfg.get("credentials", {}).get("usernames", {})
                    if not reg_username or not reg_password:
                        st.error("Username and password are required.")
                    elif reg_username in _users:
                        st.error(f"Username '{reg_username}' already exists.")
                    elif reg_password != reg_confirm:
                        st.error("Passwords do not match.")
                    else:
                        _hashed = bcrypt.hashpw(reg_password.encode(), bcrypt.gensalt(12)).decode()
                        _cfg["credentials"]["usernames"][reg_username] = {
                            "name":     reg_name or reg_username,
                            "email":    reg_email,
                            "password": _hashed,
                            "role":     "user",
                        }
                        with open(_CONFIG_PATH, "w", encoding="utf-8") as _f:
                            yaml.dump(_cfg, _f, allow_unicode=True, default_flow_style=False)
                        _reload_auth_config()
                        st.success(f"Account '{reg_username}' created. You can now log in.")

        # Hide sidebar last — injected just before render completes so sidebar
        # disappears together with page content, not before.
        st.markdown("""
        <style>
        section[data-testid="stSidebar"]      { display: none !important; }
        button[data-testid="collapsedControl"] { display: none !important; }
        </style>
        """, unsafe_allow_html=True)
        st.stop()

    # Authenticated — verify the user still exists (guards against stale cookies
    # left over after an account was deleted via User Management)
    _username = st.session_state.get("username", "")
    _fresh_config = _reload_auth_config()
    _cred = _fresh_config["credentials"]["usernames"].get(_username)
    if _cred is None:
        # Account no longer exists — force logout and clear session
        for _k in list(st.session_state.keys()):
            del st.session_state[_k]
        st.rerun()
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
_is_admin = st.session_state.get("_is_admin", False)

_nav: dict = {
    "Data": [
        st.Page("pages/00_Upload.py", title="Import Sessions", icon=":material/database_upload:"),
    ],
    "Analysis": [
        st.Page("pages/01_Session_Overview.py", title="Session Overview",
                icon=":material/expand_circle_right:", default=True),
        st.Page("pages/02_Loop_Detail.py", title="Loop Analysis", icon=":material/expand_circle_right:"),
        st.Page("pages/03_Comparison.py", title="State Transition", icon=":material/expand_circle_right:"),
        st.Page("pages/06_Session_Comparison.py", title="Fail Distribution", icon=":material/expand_circle_right:"),
    ],
}

if _is_admin:
    _nav["Tools"] = [
        st.Page("pages/04_Criteria_Tuning.py", title="Criteria Optimization", icon=":material/tune:"),
        st.Page("pages/05_User_Management.py", title="User Management", icon=":material/manage_accounts:"),
    ]

pg = st.navigation(_nav)
pg.run()
