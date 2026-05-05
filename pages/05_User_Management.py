"""
Page 5 — User Management  (admin only)
========================================
List all accounts from config/users.yaml, allow admins to delete a user.
Deleting a user also removes all their sessions and related data from DuckDB.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import yaml

if not st.session_state.get("_username"):
    st.stop()

if not st.session_state.get("_is_admin"):
    st.error("Access denied. This page is available to administrators only.")
    st.stop()

from components.sidebar import render_sidebar
from db.database import delete_sessions_by_owner, list_sessions

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "users.yaml"

render_sidebar(show_loop_selector=False, show_session_selector=False)

st.markdown("""
<style>
/* Delete button and Confirm button — alarm red */
button[kind="primary"][data-testid^="stButton"]:has(~ div),
div[data-testid="stButton"] > button[kind="primary"] {
    /* fallback — overridden by key-specific rules below */
}
/* Target any primary button whose label starts with Delete or Confirm */
[data-testid="stButton"] button[kind="primary"] {
    background-color: #D32F2F !important;
    border-color:     #D32F2F !important;
    color: #fff !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    background-color: #B71C1C !important;
    border-color:     #B71C1C !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load users
# ---------------------------------------------------------------------------
def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_config(config: dict) -> None:
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


config = _load_config()
users: dict = config.get("credentials", {}).get("usernames", {})
current_user: str = st.session_state.get("_username", "")

# ---------------------------------------------------------------------------
# User table
# ---------------------------------------------------------------------------
st.subheader("Accounts")

if not users:
    st.info("No accounts found.")
    st.stop()

for username, info in list(users.items()):
    with st.container(border=True):
        c_name, c_email, c_role, c_sessions, c_created, c_last, c_action = st.columns([2, 2, 1, 1, 2, 2, 1])
        c_name.markdown(f"**{info.get('name', username)}**  \n`{username}`")
        c_email.markdown(info.get("email", "—"))

        current_role = info.get("role", "user")
        is_self = username == current_user
        _role_options = ["user", "manager", "admin"]
        if is_self:
            # Own account — role fixed, no controls
            c_role.markdown(f"`{current_role}`")
        else:
            new_role = c_role.selectbox(
                "Role",
                _role_options,
                index=_role_options.index(current_role) if current_role in _role_options else 0,
                key=f"role_{username}",
                label_visibility="collapsed",
            )
            if new_role != current_role:
                cfg = _load_config()
                cfg["credentials"]["usernames"][username]["role"] = new_role
                _save_config(cfg)
                st.cache_resource.clear()
                st.rerun()

        own_sessions = [s for s in list_sessions(username, is_admin=True) if s["owner"] == username]
        c_sessions.metric("Sessions", len(own_sessions))
        c_created.markdown(f"**Registered**  \n{info.get('created_at', '—')}")
        c_last.markdown(f"**Last Login**  \n{info.get('last_login', '—') or '—'}")

        if is_self:
            c_action.caption("")
        else:
            if c_action.button("Delete", key=f"del_{username}", type="primary"):
                st.session_state[f"_confirm_delete_{username}"] = True

        # Confirmation step
        if st.session_state.get(f"_confirm_delete_{username}"):
            st.warning(
                f"Delete **{username}** and all their data? This cannot be undone.",
                icon=":material/warning:",
            )
            _, col_yes, col_no = st.columns([8, 1, 1])
            if col_yes.button("Confirm", key=f"yes_{username}", type="primary",
                              use_container_width=True):
                deleted = delete_sessions_by_owner(username)
                cfg = _load_config()
                cfg["credentials"]["usernames"].pop(username, None)
                _save_config(cfg)
                st.cache_resource.clear()
                st.session_state.pop(f"_confirm_delete_{username}", None)
                st.success(f"User **{username}** deleted ({deleted} session(s) removed).")
                st.rerun()
            if col_no.button("Cancel", key=f"no_{username}", use_container_width=True):
                st.session_state.pop(f"_confirm_delete_{username}", None)
                st.rerun()
