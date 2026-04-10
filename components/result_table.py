"""
Result table component — renders a styled DataFrame with colour-coded results.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.helpers import RESULT_COLORS


def _style_result(val: str) -> str:
    """Pandas Styler function for the Result column."""
    color = RESULT_COLORS.get(str(val).strip().upper(), "#888888")
    return f"background-color: {color}; color: #000; font-weight: bold;"


def render_result_table(
    df: pd.DataFrame,
    *,
    filter_result: str | None = None,
    filter_category: str | None = None,
    show_value: bool = True,
    height: int = 600,
    key: str = "result_table",
) -> None:
    """
    Render a styled test-result table with optional filtering.

    Args:
        df:              DataFrame with at least columns: Test ID, Category,
                         Test Name, Sub Item, Result, Value
        filter_result:   if set, show only rows matching this Result value
        filter_category: if set, show only rows matching this Category
        show_value:      whether to display the Value column
        height:          pixel height for the dataframe widget
        key:             unique Streamlit widget key
    """
    if df is None or df.empty:
        st.info("No data available.")
        return

    display_df = df.copy()

    # --- Filter ---
    if filter_result:
        display_df = display_df[
            display_df["Result"].fillna("").str.strip().str.upper() == filter_result.upper()
        ]
    if filter_category and filter_category != "All":
        display_df = display_df[
            display_df["Category"].fillna("") == filter_category
        ]

    if display_df.empty:
        st.info("No matching test items.")
        return

    # --- Column selection ---
    base_cols = ["Test ID", "Category", "Test Name", "Sub Item", "Result"]
    if show_value and "Value" in display_df.columns:
        base_cols.append("Value")
    existing_cols = [c for c in base_cols if c in display_df.columns]
    display_df = display_df[existing_cols].reset_index(drop=True)
    display_df = display_df.rename(columns={"Test ID": "Monitor ID"})

    # --- Styling ---
    styled = display_df.style
    if "Result" in display_df.columns:
        styled = styled.map(_style_result, subset=["Result"])

    _col_config = {
        "Monitor ID": st.column_config.NumberColumn("Monitor ID", width=90),
        "Category":   st.column_config.TextColumn("Category",    width=150),
        "Test Name":  st.column_config.TextColumn("Test Name",   width=150),
        "Sub Item":   st.column_config.TextColumn("Sub Item",    width=170),
        "Result":     st.column_config.TextColumn("Result",      width=80),
        "Value":      st.column_config.TextColumn("Value",       width=280),
    }

    st.dataframe(
        styled,
        height=height,
        width="stretch",
        column_config=_col_config,
        key=key,
    )


def render_category_filter(df: pd.DataFrame, key: str = "cat_filter") -> str:
    """
    Render a selectbox to filter by Category.

    Returns the selected category string ("All" means no filter).
    """
    if df is None or df.empty or "Category" not in df.columns:
        return "All"
    categories = ["All"] + sorted(df["Category"].dropna().unique().tolist())
    return st.selectbox("Filter by Category", categories, key=key)


def render_result_filter(key: str = "res_filter") -> str | None:
    """
    Render a selectbox to filter by Result.

    Returns None for "All".
    """
    options = ["All", "PASS", "FAIL", "BLOCK"]
    choice = st.selectbox("Filter by Result", options, key=key)
    return None if choice == "All" else choice
