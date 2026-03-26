"""
Page 4 — Criteria Tuning
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

from components.sidebar import render_sidebar
from db.database import load_log_entries
from utils.criteria_parser import CriteriaConfig
from utils.failure_analysis import analyze_failures

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MARGIN = 0.05          # 5 % headroom added beyond the worst measured value
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
        sug_min = row.get("Suggested Min")
        sug_max = row.get("Suggested Max")
        if key_min and sug_min is not None:
            cfg.set(key_min, float(sug_min))
        if key_max and sug_max is not None:
            cfg.set(key_max, float(sug_max))
    return cfg.export()


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
session_data, _ = render_sidebar(show_loop_selector=False)

st.title("Criteria Tuning")

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
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    c1.metric("Session",   session_id)
    c2.metric("Type",      log_type  or "—")
    c3.metric("Test Mode", test_mode or "—")

    if test_mode:
        hint_name = f"TestCriteria_{test_mode}.config"
        st.caption(
            f":material/info: Based on the selected session, "
            f"upload **{hint_name}**"
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
# Analysis
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Out-of-Range Failures & Suggestions")
st.caption(
    "Only parameters with **Out of Range** failures that are matched to a "
    "config key are shown.  Edit **Suggested Min / Max** before downloading."
)

with st.spinner("Analysing all loops…"):
    suggestions = _aggregate_failures(session_data, session_id, config)

if suggestions.empty:
    st.success("No out-of-range failures matched to config parameters.")
    st.stop()

# Columns visible in the editor (hide _key_* internals)
_DISPLAY_COLS = [
    "Parameter", "Root Cause", "Loops",
    "Current Min", "Current Max",
    "Actual Min",  "Actual Max",
    "Suggested Min", "Suggested Max",
]
_DISABLED_COLS = [c for c in _DISPLAY_COLS if c not in ("Suggested Min", "Suggested Max")]

_SUG_STYLE  = "background-color: #FFF3CD; color: #7B4F00; font-weight: bold;"
_ERR_STYLE  = "background-color: #FFCCCC; color: #AA0000; font-weight: bold;"

def _style_table(df: pd.DataFrame) -> pd.DataFrame:
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    # Suggested columns — orange highlight
    for col in ("Suggested Min", "Suggested Max"):
        if col in styles.columns:
            styles[col] = _SUG_STYLE
    # Act Min / Act Max — red when out of range in that direction
    if "Root Cause" in df.columns:
        for i, cause in enumerate(df["Root Cause"]):
            if "Low"  in cause or "Both" in cause:
                styles.at[df.index[i], "Actual Min"] = _ERR_STYLE
            if "High" in cause or "Both" in cause:
                styles.at[df.index[i], "Actual Max"] = _ERR_STYLE
    return styles

# Read-only display with colour highlighting (st.dataframe supports Styler)
st.dataframe(
    suggestions[_DISPLAY_COLS].style.apply(_style_table, axis=None),
    hide_index=True,
    use_container_width=True,
    column_config={
        "Parameter":     st.column_config.TextColumn("Parameter",   width=180),
        "Root Cause":    st.column_config.TextColumn("Root Cause",  width=160),
        "Loops":         st.column_config.TextColumn("Loops",       width=80),
        "Current Min":   st.column_config.NumberColumn("Cur Min",   width=90),
        "Current Max":   st.column_config.NumberColumn("Cur Max",   width=90),
        "Actual Min":    st.column_config.NumberColumn("Act Min",   width=90),
        "Actual Max":    st.column_config.NumberColumn("Act Max",   width=90),
        "Suggested Min": st.column_config.NumberColumn("Sug Min",   width=100),
        "Suggested Max": st.column_config.NumberColumn("Sug Max",   width=100),
    },
)

# Compact editable table — only the two adjustable columns
st.caption("Edit suggested values below if needed:")
edited = st.data_editor(
    suggestions[["Parameter", "Suggested Min", "Suggested Max", "_key_min", "_key_max"]],
    column_order=["Parameter", "Suggested Min", "Suggested Max"],
    disabled=["Parameter"],
    hide_index=True,
    use_container_width=True,
    column_config={
        "Parameter":     st.column_config.TextColumn("Parameter",   width=200),
        "Suggested Min": st.column_config.NumberColumn("Sug Min ✏", width=120),
        "Suggested Max": st.column_config.NumberColumn("Sug Max ✏", width=120),
    },
    key="criteria_editor",
)

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
st.divider()
_orig = suggestions.set_index("Parameter")[["Current Min", "Current Max"]]
changed_count = len(edited[
    (edited["Suggested Min"] != edited["Parameter"].map(_orig["Current Min"])) |
    (edited["Suggested Max"] != edited["Parameter"].map(_orig["Current Max"]))
])
st.caption(
    f"{changed_count} parameter(s) will be modified in the output file.  "
    f"Unchanged parameters and all comments are preserved."
)

output_name = uploaded.name
output_text = _apply_and_export(config_bytes, edited)

st.download_button(
    label="Download Tuned Config",
    data=output_text.encode("utf-8-sig"),  # BOM for Windows compatibility
    file_name=output_name,
    mime="text/plain",
    type="primary",
)
