"""
Sidebar component — session and loop selector (DB-backed, access-controlled).
"""
from __future__ import annotations

import streamlit as st

from db.database import list_sessions, load_session
from utils.helpers import get_loop_numbers


@st.cache_data(show_spinner="Loading session data…")
def _cached_load_session(session_id: str) -> dict | None:
    return load_session(session_id)


def render_sidebar(
    *,
    show_loop_selector: bool = True,
    log_root=None,  # kept for API compatibility, unused
) -> tuple[dict | None, int | None]:
    username = st.session_state.get("_username", "")
    is_admin = st.session_state.get("_is_admin", False)

    sessions = list_sessions(username, is_admin=is_admin)
    if not sessions:
        st.sidebar.warning("No sessions in database. Please import via the Upload page.")
        return None, None

    session_names = [s["session_id"] for s in sessions]
    selected_name = st.sidebar.selectbox(
        "Test Session",
        session_names,
        key="sidebar_session",
    )

    session_data = _cached_load_session(selected_name)

    selected_loop = None
    if show_loop_selector and session_data:
        loop_nums = get_loop_numbers(session_data)
        if loop_nums:
            selected_loop = st.sidebar.selectbox(
                "Loop",
                loop_nums,
                format_func=lambda n: f"Loop {n}",
                key="sidebar_loop",
            )
        else:
            st.sidebar.info("No loops found for this session.")

    st.sidebar.markdown("---")
    if session_data:
        # Show owner info for admin
        sess_meta = next((s for s in sessions if s["session_id"] == selected_name), {})
        owner = sess_meta.get("owner", "")
        st.sidebar.caption(f"Session: `{selected_name}`")
        loops_count = len(session_data.get("loops", {}))
        st.sidebar.caption(f"Loops loaded: **{loops_count}**")
        meta = session_data.get("header_meta", {})
        if meta.get("Test Mode"):
            st.sidebar.caption(f"Mode: **{meta['Test Mode']}**")
        if is_admin and owner:
            st.sidebar.caption(f"Owner: `{owner}`")

    return session_data, selected_loop
