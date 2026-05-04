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
    show_session_selector: bool = True,
    log_root=None,  # kept for API compatibility, unused
) -> tuple[dict | None, int | None]:
    username = st.session_state.get("_username", "")
    is_admin = st.session_state.get("_is_admin", False)

    sessions = list_sessions(username, is_admin=is_admin)
    if not sessions:
        st.sidebar.warning("No sessions in database. Please import via the Upload page.")
        return None, None

    if not show_session_selector:
        return None, None

    # --- Log type filter (radio) ---
    # Only shown when there are 2+ distinct non-empty log types in the session list.
    _available_types = sorted({s["log_type"] for s in sessions if s.get("log_type")})
    if len(_available_types) >= 2:
        _persisted_type = st.session_state.get("_sidebar_log_type")
        _type_index = (
            _available_types.index(_persisted_type)
            if _persisted_type in _available_types
            else 0
        )
        selected_type = st.sidebar.radio(
            "Type",
            _available_types,
            index=_type_index,
            horizontal=True,
            key="sidebar_log_type",
        )
        st.session_state["_sidebar_log_type"] = selected_type
        filtered_sessions = [s for s in sessions if s.get("log_type") == selected_type]
        if not filtered_sessions:
            filtered_sessions = sessions
    else:
        filtered_sessions = sessions

    session_ids = [s["session_id"] for s in filtered_sessions]

    # Build display labels: prepend [log_type] when available
    _label_map = {
        s["session_id"]: (
            f"[{s['log_type']}] {s['session_id']}" if s.get("log_type") else s["session_id"]
        )
        for s in filtered_sessions
    }

    # st.navigation() clears widget-bound keys on page switch, so we cannot
    # rely on "sidebar_session" to survive navigation.  Instead we persist the
    # selected session_id in a plain (non-widget) key that Streamlit never
    # touches automatically.
    _persisted = st.session_state.get("_sidebar_session_id")
    if isinstance(_persisted, str) and _persisted in session_ids:
        _default_index = session_ids.index(_persisted)
    else:
        _default_index = 0

    selected_name = st.sidebar.selectbox(
        "Test Session",
        session_ids,
        format_func=lambda sid: _label_map[sid],
        index=_default_index,
        key="sidebar_session",
    )
    # Keep the non-widget key in sync so it survives the next page switch.
    st.session_state["_sidebar_session_id"] = selected_name

    session_data = _cached_load_session(selected_name)

    selected_loop = None
    if show_loop_selector and session_data:
        loop_nums = get_loop_numbers(session_data)
        if loop_nums:
            _persisted_loop = st.session_state.get("_sidebar_loop_num")
            _loop_index = (
                loop_nums.index(_persisted_loop)
                if _persisted_loop in loop_nums
                else 0
            )
            selected_loop = st.sidebar.selectbox(
                "Loop",
                loop_nums,
                format_func=lambda n: f"Loop {n}",
                index=_loop_index,
                key="sidebar_loop",
            )
            st.session_state["_sidebar_loop_num"] = selected_loop
        else:
            st.sidebar.info("No loops found for this session.")

    if session_data:
        sess_meta = next((s for s in sessions if s["session_id"] == selected_name), {})
        st.session_state["_session_log_type"] = sess_meta.get("log_type", "")

    return session_data, selected_loop
