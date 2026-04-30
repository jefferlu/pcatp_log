"""
Page 4 — Criteria Optimization
=========================
Upload a TestCriteria_*.config, automatically suggest adjusted _Min/_Max
values based on out-of-range failures across all loops of the selected
session, and download a corrected config file.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

if not st.session_state.get("_username"):
    st.stop()

if not st.session_state.get("_is_admin"):
    st.error("Access denied. This page is available to administrators only.")
    st.stop()

from components.sidebar import render_sidebar
from db.database import load_log_entries
from utils.criteria_parser import CriteriaConfig
from utils.failure_analysis import analyze_failures

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MARGIN = 0.20          # 20 % headroom added beyond the worst measured value
_OOR    = "Out of Range"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Normalize a parameter name for matching (upper, spaces → '_')."""
    return re.sub(r"[\s\-]+", "_", s.strip().upper())


def _build_base_map(config: CriteriaConfig) -> dict[str, tuple[str, str]]:
    """Return {norm_base: (key_min, key_max)} for all pairs in the config."""
    base_map: dict[str, tuple[str, str]] = {}
    for key in config.params:
        base    = key[:-4]          # strip '_Max' or '_Min'
        norm    = _norm(base)
        entry   = base_map.get(norm, ("", ""))
        if key.endswith("_Min"):
            base_map[norm] = (key,        entry[1])
        else:
            base_map[norm] = (entry[0],   key)
    return base_map


def _aggregate_failures(
    session_data: dict,
    session_id: str,
    config: CriteriaConfig,
) -> pd.DataFrame:
    """
    Iterate all loops, run Failure Analysis, and aggregate worst-case
    out-of-range actuals for each matched config parameter.

    Returns a DataFrame ready for st.data_editor.
    """
    base_map = _build_base_map(config)
    params   = config.params

    # worst[norm_base] → {base, act_min, act_max, lo, hi, loops, cause}
    worst: dict[str, dict] = {}

    loops = session_data.get("loops", {})
    for loop_num, ldata in sorted(loops.items()):
        results_df  = ldata.get("results", pd.DataFrame())
        log_entries = load_log_entries(session_id, loop_num)

        if results_df.empty:
            continue

        fa_df = analyze_failures(results_df, log_entries)
        if fa_df.empty:
            continue

        for _, row in fa_df.iterrows():
            cause = str(row.get("Root Cause", ""))
            if _OOR not in cause:
                continue

            actual_str = str(row.get("Actual", ""))
            limit_str  = str(row.get("Limit",  ""))

            # limit is always "lo ~ hi"
            l_m = re.match(r"([\d.]+)\s*~\s*([\d.]+)", limit_str)
            if not l_m:
                continue

            # actual can be "lo ~ hi" (range) or "Avg: X" (single point)
            a_range = re.match(r"([\d.]+)\s*~\s*([\d.]+)", actual_str)
            a_avg   = re.search(r"Avg:\s*([\d.]+)", actual_str)
            if a_range:
                act_min = float(a_range.group(1))
                act_max = float(a_range.group(2))
            elif a_avg:
                act_min = act_max = float(a_avg.group(1))
            else:
                continue

            # Try Sub Item first, then Test Name
            matched_norm = None
            matched_base = None
            for candidate in (
                str(row.get("Sub Item",  "")).strip(),
                str(row.get("Test Name", "")).strip(),
            ):
                n = _norm(candidate)
                if n in base_map:
                    matched_norm = n
                    matched_base = candidate
                    break

            if matched_norm is None:
                continue

            if matched_norm not in worst:
                worst[matched_norm] = {
                    "base":    matched_base,
                    "act_min": act_min,
                    "act_max": act_max,
                    "loops":   [loop_num],
                    "cause":   cause,
                }
            else:
                w = worst[matched_norm]
                w["act_min"] = min(w["act_min"], act_min)
                w["act_max"] = max(w["act_max"], act_max)
                if loop_num not in w["loops"]:
                    w["loops"].append(loop_num)

    # Build suggestion rows
    rows = []
    for norm, w in worst.items():
        key_min, key_max = base_map[norm]
        cur_min = params.get(key_min)
        cur_max = params.get(key_max)
        act_min = w["act_min"]
        act_max = w["act_max"]
        cause   = w["cause"]

        # Only adjust the direction(s) that are out of range
        if cur_min is not None and act_min < cur_min:
            margin  = abs(act_min) * _MARGIN if act_min != 0 else _MARGIN
            sug_min = round(act_min - margin, 2)
        else:
            sug_min = cur_min

        if cur_max is not None and act_max > cur_max:
            margin  = abs(act_max) * _MARGIN if act_max != 0 else _MARGIN
            sug_max = round(act_max + margin, 2)
        else:
            sug_max = cur_max

        rows.append({
            "Parameter":     w["base"],
            "Root Cause":    cause,
            "Loops":         ", ".join(str(l) for l in sorted(w["loops"])),
            "Current Min":   cur_min,
            "Current Max":   cur_max,
            "Actual Min":    round(act_min, 2),
            "Actual Max":    round(act_max, 2),
            "Suggested Min": sug_min,
            "Suggested Max": sug_max,
            # Hidden: needed when applying changes
            "_key_min":      key_min,
            "_key_max":      key_max,
        })

    return pd.DataFrame(rows)


def _apply_and_export(config_bytes: bytes, edited_df: pd.DataFrame) -> str:
    """Build a fresh CriteriaConfig from original bytes and apply edits."""
    cfg = CriteriaConfig.from_bytes(config_bytes)
    for _, row in edited_df.iterrows():
        key_min = row.get("_key_min", "")
        key_max = row.get("_key_max", "")
        new_min = row.get("Current Min")
        new_max = row.get("Current Max")
        if key_min and new_min is not None:
            cfg.set(key_min, float(new_min))
        if key_max and new_max is not None:
            cfg.set(key_max, float(new_max))
    return cfg.export()


def _build_bulk_table(config: CriteriaConfig) -> pd.DataFrame:
    """Return a DataFrame of all Min/Max pairs with +MARGIN applied."""
    base_map = _build_base_map(config)
    rows = []
    for _, (key_min, key_max) in sorted(base_map.items()):
        cur_min = config.params.get(key_min)
        cur_max = config.params.get(key_max)
        if cur_min is None and cur_max is None:
            continue
        base_name = (key_min[:-4] if key_min else key_max[:-4])
        if cur_min is not None:
            m = abs(cur_min) * _MARGIN if cur_min != 0 else _MARGIN
            adj_min = round(cur_min - m, 2)
        else:
            adj_min = None
        if cur_max is not None:
            m = abs(cur_max) * _MARGIN if cur_max != 0 else _MARGIN
            adj_max = round(cur_max + m, 2)
        else:
            adj_max = None
        rows.append({
            "Parameter":    base_name,
            "Current Min":  cur_min,
            "Current Max":  cur_max,
            "Adjusted Min": adj_min,
            "Adjusted Max": adj_max,
            "_key_min":     key_min,
            "_key_max":     key_max,
        })
    return pd.DataFrame(rows)


def _apply_bulk_export(config_bytes: bytes, bulk_df: pd.DataFrame) -> str:
    """Apply all bulk-adjusted values to a fresh config and export."""
    cfg = CriteriaConfig.from_bytes(config_bytes)
    for _, row in bulk_df.iterrows():
        if row["_key_min"] and row["Adjusted Min"] is not None:
            cfg.set(row["_key_min"], float(row["Adjusted Min"]))
        if row["_key_max"] and row["Adjusted Max"] is not None:
            cfg.set(row["_key_max"], float(row["Adjusted Max"]))
    return cfg.export()


def _apply_suggestions_export(config_bytes: bytes, sugg_df: pd.DataFrame) -> str:
    """Apply failure-based suggested values to a fresh config and export."""
    cfg = CriteriaConfig.from_bytes(config_bytes)
    for _, row in sugg_df.iterrows():
        key_min = row.get("_key_min", "")
        key_max = row.get("_key_max", "")
        new_min = row.get("Suggested Min")
        new_max = row.get("Suggested Max")
        if key_min and pd.notna(new_min):
            cfg.set(key_min, float(new_min))
        if key_max and pd.notna(new_max):
            cfg.set(key_max, float(new_max))
    return cfg.export()


# ---------------------------------------------------------------------------
# Window Shift helpers
# ---------------------------------------------------------------------------

def _adjust_window(avg: float, old_min: float, old_max: float) -> tuple[float, float]:
    """Center [old_min, old_max] around avg; floor at 0."""
    half_width = (old_max - old_min) / 2
    h = min(half_width, avg)
    return round(max(avg - h, 0), 4), round(avg + h, 4)


_AVG_RE = re.compile(r"Avg:([\d.Ee+\-]+)")
_NUM_RE = re.compile(r"^[\d.Ee+\-]+$")


def _parse_actual(val: str) -> float | None:
    """Extract a single numeric value from a result Value string."""
    try:
        m = _AVG_RE.search(val)
        if m:
            return float(m.group(1))
        v = val.split("|")[0].strip()
        if _NUM_RE.match(v):
            return float(v)
    except (ValueError, TypeError):
        pass
    return None


def _aggregate_window_shift(
    session_data: dict,
    session_id: str,
    config: CriteriaConfig,
) -> pd.DataFrame:
    """
    For each config parameter, collect actual values from ALL loops (pass and
    fail), compute the overall mean, then apply window-shift centering.

    Rules:
      - Only parameters with both Min AND Max in the config.
      - Skip parameters where Min=0 and Max=60 (binary/boolean limits).
      - New Min is floored at 0.
    """
    base_map = _build_base_map(config)
    params   = config.params

    # norm → {base, values: list[float], loop_count: int}
    actuals: dict[str, dict] = {}

    loops = session_data.get("loops", {})
    for loop_num, ldata in sorted(loops.items()):
        results_df = ldata.get("results", pd.DataFrame())
        if results_df.empty:
            continue

        for _, row in results_df.iterrows():
            val = _parse_actual(str(row.get("Value", "") or ""))
            if val is None:
                continue

            matched_norm = None
            matched_base = None
            for candidate in (
                str(row.get("Sub Item",  "")).strip(),
                str(row.get("Test Name", "")).strip(),
            ):
                n = _norm(candidate)
                if n in base_map:
                    matched_norm = n
                    matched_base = candidate
                    break

            if matched_norm is None:
                continue

            if matched_norm not in actuals:
                actuals[matched_norm] = {
                    "base":       matched_base,
                    "values":     [val],
                    "loop_count": 0,
                }
            else:
                actuals[matched_norm]["values"].append(val)

        # Increment loop_count once per norm per loop
        seen_norms = set()
        for _, row in results_df.iterrows():
            for candidate in (
                str(row.get("Sub Item",  "")).strip(),
                str(row.get("Test Name", "")).strip(),
            ):
                n = _norm(candidate)
                if n in actuals and n not in seen_norms:
                    actuals[n]["loop_count"] += 1
                    seen_norms.add(n)
                    break

    rows = []
    for norm, w in actuals.items():
        key_min, key_max = base_map[norm]
        cur_min = params.get(key_min)
        cur_max = params.get(key_max)

        if cur_min is None or cur_max is None:
            continue
        if cur_min == 0 and cur_max == 50:
            continue

        avg_actual = sum(w["values"]) / len(w["values"])
        new_min, new_max = _adjust_window(avg_actual, cur_min, cur_max)

        rows.append({
            "Parameter":   w["base"],
            "Loops":       w["loop_count"],
            "Avg Actual":  round(avg_actual, 4),
            "Current Min": cur_min,
            "Current Max": cur_max,
            "New Min":     new_min,
            "New Max":     new_max,
            "_key_min":    key_min,
            "_key_max":    key_max,
        })

    return pd.DataFrame(rows)


def _apply_window_shift_export(config_bytes: bytes, ws_df: pd.DataFrame) -> str:
    cfg = CriteriaConfig.from_bytes(config_bytes)
    for _, row in ws_df.iterrows():
        key_min = row.get("_key_min", "")
        key_max = row.get("_key_max", "")
        new_min = row.get("New Min")
        new_max = row.get("New Max")
        if key_min and pd.notna(new_min):
            cfg.set(key_min, float(new_min))
        if key_max and pd.notna(new_max):
            cfg.set(key_max, float(new_max))
    return cfg.export()


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
session_data, _ = render_sidebar(show_loop_selector=False)

if session_data is None:
    st.info("Select a session from the sidebar.")
    st.stop()

session_id = session_data["id"]
test_mode  = session_data.get("header_meta", {}).get("Test Mode", "").strip()
sess_meta  = next(
    (s for s in __import__("db.database", fromlist=["list_sessions"])
     .list_sessions(
         st.session_state.get("_username", ""),
         is_admin=st.session_state.get("_is_admin", False),
     ) if s["session_id"] == session_id),
    {},
)
log_type = sess_meta.get("log_type", "")

# ---------------------------------------------------------------------------
# Session info + upload hint
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    [data-testid="stMetricLabel"] { font-size: 0.7rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.75rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    c1.metric("Session",   session_id)
    c2.metric("Type",      log_type  or "—")
    c3.metric("Test Mode", test_mode or "—")

    if test_mode:
        hint_name = f"TestCriteria_{test_mode}.config"
        st.caption(
            f":material/info: Based on the selected session, "
            f"upload *{hint_name}*"
            + (f" from the **{log_type}** config directory." if log_type else ".")
        )

# ---------------------------------------------------------------------------
# Config upload
# ---------------------------------------------------------------------------
uploaded = st.file_uploader(
    "Upload TestCriteria config file",
    type=["config"],
    key="criteria_upload",
)

if uploaded is None:
    st.stop()

config_bytes = uploaded.read()
config       = CriteriaConfig.from_bytes(config_bytes)

st.success(
    f"Loaded **{uploaded.name}** — "
    f"{len(config.params)} tunable parameters found."
)

# ---------------------------------------------------------------------------
# Analyse failures (needed by window-shift and failure tabs)
# ---------------------------------------------------------------------------
with st.spinner("Analysing all loops…"):
    suggestions      = _aggregate_failures(session_data, session_id, config)
    window_shift_df  = _aggregate_window_shift(session_data, session_id, config)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
st.divider()
tab_all, tab_bulk, tab_win, tab_fail = st.tabs([
    "All Parameters",
    f"Bulk +{int(_MARGIN*100)}% Margin",
    "Window Shift",
    "Failure-Based Suggestions",
])

# ---------------------------------------------------------------------------
# Tab 0 — All Parameters
# ---------------------------------------------------------------------------
with tab_all:
    st.caption("All tunable parameters in the config. Edit Min / Max then download.")
    _base_map = _build_base_map(config)
    _all_rows = []
    for _, (key_min, key_max) in sorted(_base_map.items()):
        cur_min = config.params.get(key_min)
        cur_max = config.params.get(key_max)
        if cur_min is None and cur_max is None:
            continue
        base_name = key_min[:-4] if key_min else key_max[:-4]
        _all_rows.append({
            "Parameter":   base_name,
            "Current Min": cur_min,
            "Current Max": cur_max,
            "_key_min":    key_min,
            "_key_max":    key_max,
        })
    _all_df = pd.DataFrame(_all_rows)

    _orig_min_map = _all_df.set_index("Parameter")["Current Min"].to_dict() if not _all_df.empty else {}
    _orig_max_map = _all_df.set_index("Parameter")["Current Max"].to_dict() if not _all_df.empty else {}

    edited_all = st.data_editor(
        _all_df,
        column_order=["Parameter", "Current Min", "Current Max"],
        disabled=["Parameter"],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Parameter":   st.column_config.TextColumn("Parameter",  width=220),
            "Current Min": st.column_config.NumberColumn("Min ✏",    width=130),
            "Current Max": st.column_config.NumberColumn("Max ✏",    width=130),
        },
        key="all_params_editor",
    )

    _changed = 0
    if not edited_all.empty:
        _changed = len(edited_all[
            (edited_all["Current Min"] != edited_all["Parameter"].map(_orig_min_map)) |
            (edited_all["Current Max"] != edited_all["Parameter"].map(_orig_max_map))
        ])
    st.caption(
        f"{_changed} parameter(s) will be modified.  "
        "Unchanged parameters and all comments are preserved."
    )
    st.download_button(
        label="Download Tuned Config",
        data=_apply_and_export(config_bytes, edited_all).encode("utf-8-sig") if not edited_all.empty else config_bytes,
        file_name=uploaded.name,
        mime="text/plain",
        type="primary",
        key="dl_all",
    )

# ---------------------------------------------------------------------------
# Tab 1 — Window Shift
# ---------------------------------------------------------------------------
with tab_win:
    st.caption(
        "Centers the existing [Min, Max] window around the **mean actual value** "
        "across all fail loops.  Min is floored at 0.  "
        "Parameters with only Min or Max (no pair) and Limit[0~50] are excluded."
    )
    if window_shift_df.empty:
        st.success("No out-of-range failures matched to paired config parameters.")
    else:
        _WIN_COLS = [
            "Parameter", "Loops", "Avg Actual",
            "Current Min", "Current Max",
            "New Min", "New Max",
            "_key_min", "_key_max",
        ]
        edited_win = st.data_editor(
            window_shift_df[_WIN_COLS],
            column_order=[c for c in _WIN_COLS if not c.startswith("_")],
            disabled=["Parameter", "Loops", "Avg Actual", "Current Min", "Current Max"],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Parameter":   st.column_config.TextColumn("Parameter",    width=200),
                "Loops":       st.column_config.TextColumn("Loops",        width=80),
                "Avg Actual":  st.column_config.NumberColumn("Avg Actual", width=100, format="%.4f"),
                "Current Min": st.column_config.NumberColumn("Cur Min",    width=90),
                "Current Max": st.column_config.NumberColumn("Cur Max",    width=90),
                "New Min":     st.column_config.NumberColumn("New Min ✏",  width=100),
                "New Max":     st.column_config.NumberColumn("New Max ✏",  width=100),
            },
            key="win_editor",
        )
        st.download_button(
            label="Download Window-Shift Config",
            data=_apply_window_shift_export(config_bytes, edited_win).encode("utf-8-sig"),
            file_name=uploaded.name,
            mime="text/plain",
            type="primary",
            key="dl_win",
        )

# ---------------------------------------------------------------------------
# Tab 2 — Failure-Based
# ---------------------------------------------------------------------------
with tab_fail:
    st.caption("Parameters with **Out of Range** failures matched to a config key.")
    if suggestions.empty:
        st.success("No out-of-range failures matched to config parameters.")
    else:
        _SUGG_COLS = [
            "Parameter", "Root Cause", "Loops",
            "Current Min", "Current Max",
            "Actual Min",  "Actual Max",
            "Suggested Min", "Suggested Max",
            "_key_min", "_key_max",
        ]
        edited_sugg = st.data_editor(
            suggestions[_SUGG_COLS],
            column_order=[c for c in _SUGG_COLS if not c.startswith("_")],
            disabled=["Parameter", "Root Cause", "Loops",
                      "Current Min", "Current Max", "Actual Min", "Actual Max"],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Parameter":     st.column_config.TextColumn("Parameter",    width=180),
                "Root Cause":    st.column_config.TextColumn("Root Cause",   width=160),
                "Loops":         st.column_config.TextColumn("Loops",        width=80),
                "Current Min":   st.column_config.NumberColumn("Cur Min",    width=90),
                "Current Max":   st.column_config.NumberColumn("Cur Max",    width=90),
                "Actual Min":    st.column_config.NumberColumn("Act Min",    width=90),
                "Actual Max":    st.column_config.NumberColumn("Act Max",    width=90),
                "Suggested Min": st.column_config.NumberColumn("Sug Min ✏", width=100),
                "Suggested Max": st.column_config.NumberColumn("Sug Max ✏", width=100),
            },
            key="sugg_editor",
        )
        st.download_button(
            label="Download Suggestion-Based Config",
            data=_apply_suggestions_export(config_bytes, edited_sugg).encode("utf-8-sig"),
            file_name=uploaded.name,
            mime="text/plain",
            type="primary",
            key="dl_fail_sugg",
        )

# ---------------------------------------------------------------------------
# Tab 2 — Bulk Margin
# ---------------------------------------------------------------------------
with tab_bulk:
    st.caption(
        f"Every parameter in the config is widened by **{int(_MARGIN*100)}%** "
        f"(Min − {int(_MARGIN*100)}%, Max + {int(_MARGIN*100)}%).  "
        "Adjust individual values before downloading."
    )

    bulk_df = _build_bulk_table(config)

    _BULK_COLS = ["Parameter", "Current Min", "Current Max", "Adjusted Min", "Adjusted Max",
                  "_key_min", "_key_max"]
    edited_bulk = st.data_editor(
        bulk_df[_BULK_COLS],
        column_order=["Parameter", "Current Min", "Current Max", "Adjusted Min", "Adjusted Max"],
        disabled=["Parameter", "Current Min", "Current Max"],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Parameter":    st.column_config.TextColumn("Parameter",     width=220),
            "Current Min":  st.column_config.NumberColumn("Cur Min",     width=100),
            "Current Max":  st.column_config.NumberColumn("Cur Max",     width=100),
            "Adjusted Min": st.column_config.NumberColumn("Adj Min ✏",  width=100),
            "Adjusted Max": st.column_config.NumberColumn("Adj Max ✏",  width=100),
        },
        key="bulk_editor",
    )

    st.caption(
        f"{len(bulk_df)} parameter pair(s).  "
        "All comments and non-tunable lines are preserved."
    )
    st.download_button(
        label="Download Bulk-Adjusted Config",
        data=_apply_bulk_export(config_bytes, edited_bulk).encode("utf-8-sig"),
        file_name=uploaded.name,
        mime="text/plain",
        type="primary",
        key="dl_bulk",
    )
