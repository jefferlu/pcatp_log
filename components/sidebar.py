"""
Sidebar component — session and loop selector.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from utils.helpers import discover_sessions, get_loop_numbers
from parsers.csv_parser import load_session


# Session data is cached so it's shared across pages within a run.
@st.cache_data(show_spinner="Loading session data…")
def _cached_load_session(session_path: str) -> dict:
    return load_session(Path(session_path))


def render_sidebar(
    *,
    show_loop_selector: bool = True,
    log_root: Path | None = None,
) -> tuple[dict | None, int | None]:
    """
    Render the sidebar with session and (optionally) loop selectors.

    Returns:
        session_data : loaded session dict, or None if no sessions found
        selected_loop: int loop number, or None
    """
    st.sidebar.title("ATP Log Analyzer")
    st.sidebar.markdown("---")

    sessions = discover_sessions(log_root)
    if not sessions:
        st.sidebar.warning("No sessions found in .log_files/")
        return None, None

    session_names = [s.name for s in sessions]
    selected_name = st.sidebar.selectbox(
        "Test Session",
        session_names,
        key="sidebar_session",
    )
    selected_path = next(s for s in sessions if s.name == selected_name)

    session_data = _cached_load_session(str(selected_path))

    selected_loop = None
    if show_loop_selector:
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

    # Show quick summary in sidebar
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Session: `{selected_name}`")
    loops_count = len(session_data.get("loops", {}))
    st.sidebar.caption(f"Loops loaded: **{loops_count}**")

    meta = session_data.get("header_meta", {})
    if meta.get("Test Mode"):
        st.sidebar.caption(f"Mode: **{meta['Test Mode']}**")

    return session_data, selected_loop
