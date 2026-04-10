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

render_sidebar(show_loop_selector=False)

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
        c_name, c_email, c_role, c_sessions, c_action = st.columns([2, 3, 1, 1, 1])
        c_name.markdown(f"**{info.get('name', username)}**  \n`{username}`")
        c_email.markdown(info.get("email", "—"))
        c_role.markdown(f"`{info.get('role', 'user')}`")

        session_count = len(list_sessions(username, is_admin=True))
        # filter to only this user's own sessions
        own_sessions = [s for s in list_sessions(username, is_admin=True) if s["owner"] == username]
        c_sessions.metric("Sessions", len(own_sessions))

        if username == current_user:
            c_action.caption("(you)")
        else:
            if c_action.button("Delete", key=f"del_{username}", type="primary"):
                st.session_state[f"_confirm_delete_{username}"] = True

        # Confirmation step
        if st.session_state.get(f"_confirm_delete_{username}"):
            st.warning(
                f"Delete **{username}** and all their data? This cannot be undone.",
                icon=":material/warning:",
            )
            col_yes, col_no = st.columns(2)
            if col_yes.button("Yes, delete", key=f"yes_{username}", type="primary"):
                deleted = delete_sessions_by_owner(username)
                cfg = _load_config()
                cfg["credentials"]["usernames"].pop(username, None)
                _save_config(cfg)
                st.session_state.pop(f"_confirm_delete_{username}", None)
                st.success(f"User **{username}** deleted ({deleted} session(s) removed).")
                st.rerun()
            if col_no.button("Cancel", key=f"no_{username}"):
                st.session_state.pop(f"_confirm_delete_{username}", None)
                st.rerun()
