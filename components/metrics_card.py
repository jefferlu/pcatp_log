"""
Metrics card component — shows PASS / FAIL / BLOCK / Total counts.
"""
from __future__ import annotations

import streamlit as st


def render_metrics_card(
    total: int,
    passed: int,
    failed: int,
    blocked: int,
    *,
    title: str = "Test Summary",
) -> None:
    """
    Render a row of four metric columns: Total, Passed, Failed, Blocked.

    Args:
        total:   total number of test items executed (passed + failed + blocked)
        passed:  number of PASS results
        failed:  number of FAIL results
        blocked: number of BLOCK results
        title:   optional section title above the metrics
    """
    if title:
        st.subheader(title)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total", total)
    with col2:
        pass_pct = f"{passed / total * 100:.1f}%" if total else "—"
        st.metric("✅ Passed", passed, delta=pass_pct, delta_color="normal")
    with col3:
        fail_pct = f"{failed / total * 100:.1f}%" if total else "—"
        st.metric("❌ Failed", failed, delta=fail_pct, delta_color="inverse")
    with col4:
        blk_pct = f"{blocked / total * 100:.1f}%" if total else "—"
        st.metric("🚫 Blocked", blocked, delta=blk_pct, delta_color="off")


def compute_counts(results_df) -> dict:
    """
    Compute PASS/FAIL/BLOCK/Total counts from a results DataFrame.

    Returns dict with keys: total, passed, failed, blocked.
    """
    if results_df is None or results_df.empty:
        return {"total": 0, "passed": 0, "failed": 0, "blocked": 0}

    col = "Result"
    if col not in results_df.columns:
        return {"total": 0, "passed": 0, "failed": 0, "blocked": 0}

    results = results_df[col].fillna("").str.strip().str.upper()
    passed  = int((results == "PASS").sum())
    failed  = int((results == "FAIL").sum())
    blocked = int((results == "BLOCK").sum())
    total   = passed + failed + blocked

    return {"total": total, "passed": passed, "failed": failed, "blocked": blocked}
