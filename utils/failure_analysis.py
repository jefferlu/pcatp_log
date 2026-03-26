"""
Failure root-cause analysis utilities.

Links CSV test results (results_df) to TXT log entries to classify
why each FAIL / BLOCK test item failed.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Value field parsers
# ---------------------------------------------------------------------------

_RANGE_RE = re.compile(
    r"Min:([\d.Ee+\-]+)\s+Max:([\d.Ee+\-]+)\s*\|\s*Limit\[([\d.Ee+\-]+)~([\d.Ee+\-]+)\]"
)
_AVG_LIMIT_RE = re.compile(
    r"Avg:([\d.Ee+\-]+)\s*\|\s*Limit\[([\d.Ee+\-]+)~([\d.Ee+\-]+)\]"
)
_CMP_RE = re.compile(r"Cur:([\d.Ee+\-]+)\s*\|\s*Exp:([\d.Ee+\-]+)")


def _parse_value(value_str: str) -> dict:
    s = value_str.strip()
    m = _RANGE_RE.search(s)
    if m:
        return {
            "type":     "range",
            "min_val":  float(m.group(1)),
            "max_val":  float(m.group(2)),
            "lo_limit": float(m.group(3)),
            "hi_limit": float(m.group(4)),
        }
    m = _AVG_LIMIT_RE.search(s)
    if m:
        return {
            "type":     "avg_limit",
            "avg_val":  float(m.group(1)),
            "lo_limit": float(m.group(2)),
            "hi_limit": float(m.group(3)),
        }
    m = _CMP_RE.search(s)
    if m:
        return {
            "type":    "compare",
            "cur_val": float(m.group(1)),
            "exp_val": float(m.group(2)),
        }
    return {"type": "unknown"}


def _classify_root_cause(result: str, parsed: dict, category: str = "") -> str:
    if result in ("BLOCK", "BLOCKED"):
        return "Blocked"
    if parsed["type"] == "range":
        mn, mx = parsed["min_val"], parsed["max_val"]
        lo, hi = parsed["lo_limit"], parsed["hi_limit"]
        over  = mx > hi
        under = mn < lo
        if over and under:
            return "Out of Range (Both)"
        if over:
            return "Out of Range (High)"
        if under:
            return "Out of Range (Low)"
        return "Out of Range"
    if parsed["type"] == "avg_limit":
        avg = parsed["avg_val"]
        lo, hi = parsed["lo_limit"], parsed["hi_limit"]
        if avg > hi:
            return "Out of Range (High)"
        if avg < lo:
            return "Out of Range (Low)"
        return "Out of Range"
    if parsed["type"] == "compare":
        return "Value Mismatch"
    return "Unknown"


def _format_deviation(parsed: dict) -> str:
    if parsed["type"] == "range":
        mn, mx = parsed["min_val"], parsed["max_val"]
        lo, hi = parsed["lo_limit"], parsed["hi_limit"]
        if hi != 0 and mx > hi:
            return f"+{(mx - hi) / hi * 100:.1f}%"
        if lo != 0 and mn < lo:
            return f"-{(lo - mn) / lo * 100:.1f}%"
    if parsed["type"] == "avg_limit":
        avg = parsed["avg_val"]
        lo, hi = parsed["lo_limit"], parsed["hi_limit"]
        if hi != 0 and avg > hi:
            return f"+{(avg - hi) / hi * 100:.1f}%"
        if lo != 0 and avg < lo:
            return f"-{(lo - avg) / lo * 100:.1f}%"
    return ""


# ---------------------------------------------------------------------------
# Log index builder
# ---------------------------------------------------------------------------

_UDP_RE     = re.compile(r"ID:([0-9A-Fa-f]+)\s+\(([^)]+)\)\s*\|\s*(.*)")
_FAIL_RE    = re.compile(r"(.+?)\s+\(0x([0-9A-Fa-f]+)\):\s*(.*)")
_RETRY_RE   = re.compile(r"FAIL detected \(([^)]+)\),\s*retry\s*(\d+)/(\d+)")
_NUMERIC_RE = re.compile(
    r"Cur:([\d.Ee+\-]+)\s+Avg:([\d.Ee+\-]+)\s+Min:([\d.Ee+\-]+)\s+Max:([\d.Ee+\-]+)"
)


def _build_log_index(log_entries: list[dict]) -> dict:
    """Build lookup structures from log entries for fast cross-referencing."""
    udp:         dict[str, dict] = {}   # HEX_ID -> {name, cur, avg, min, max} or {name, raw}
    fail_msgs:   dict[str, str]  = {}   # HEX_ID -> reason string
    retry:       dict[str, int]  = {}   # channel -> max retry count seen
    no_response: list[str]       = []
    blocked_proc: list[str]      = []

    for e in log_entries:
        mod = e.get("module", "").strip()
        msg = e.get("message", "")

        if mod == "UDP Data":
            m = _UDP_RE.match(msg)
            if m:
                hid     = m.group(1).upper()
                payload = m.group(3)
                entry: dict[str, Any] = {"name": m.group(2)}
                mn = _NUMERIC_RE.search(payload)
                if mn:
                    entry.update({
                        "cur": float(mn.group(1)), "avg": float(mn.group(2)),
                        "min": float(mn.group(3)), "max": float(mn.group(4)),
                    })
                else:
                    rm = re.search(r"RawData:([0-9A-Fa-f\-]+)", payload)
                    entry["raw"] = rm.group(1) if rm else payload
                udp[hid] = entry

        elif mod == "FAIL":
            m = _FAIL_RE.match(msg)
            if m:
                hid = m.group(2).upper()
                fail_msgs[hid] = m.group(3).strip()

        elif "CAN" in mod.upper():
            if "No CAN result found" in msg:
                no_response.append(msg)
            else:
                m = _RETRY_RE.search(msg)
                if m:
                    ch  = m.group(1)
                    cnt = int(m.group(2))
                    retry[ch] = max(retry.get(ch, 0), cnt)

        elif "PROC" in mod.upper():
            if any(kw in msg for kw in ("not connected", "Skipping", "Skip –")):
                blocked_proc.append(msg)

    return {
        "udp":          udp,
        "fail_msgs":    fail_msgs,
        "retry":        retry,
        "no_response":  no_response,
        "blocked_proc": blocked_proc,
    }


# ---------------------------------------------------------------------------
# Root-cause badge colors (for display)
# ---------------------------------------------------------------------------

ROOT_CAUSE_COLOR = {
    "Out of Range (High)": "#EE3333",
    "Out of Range (Low)":  "#3399EE",
    "Out of Range (Both)": "#AA33EE",
    "Out of Range":        "#EE3333",
    "Value Mismatch":      "#DD8800",
    "No Response":         "#666666",
    "Blocked":             "#DD8800",
    "Unknown":             "#999999",
}

ROOT_CAUSE_ICON = {
    "Out of Range (High)": "↑",
    "Out of Range (Low)":  "↓",
    "Out of Range (Both)": "↕",
    "Out of Range":        "✗",
    "Value Mismatch":      "≠",
    "No Response":         "—",
    "Blocked":             "⊘",
    "Unknown":             "?",
}


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def analyze_failures(
    results_df: pd.DataFrame,
    log_entries: list[dict],
) -> pd.DataFrame:
    """
    For each FAIL / BLOCK row in results_df, produce an enriched dict with
    root-cause classification drawn from the matched TXT log entries.

    Returns DataFrame with columns:
        Test ID | Category | Test Name | Sub Item |
        Root Cause | Actual | Limit | Deviation | Log Evidence
    """
    if results_df.empty:
        return pd.DataFrame()

    idx = _build_log_index(log_entries)
    rows = []

    for _, row in results_df.iterrows():
        result   = str(row.get("Result", "")).strip().upper()
        if result not in ("FAIL", "BLOCK", "BLOCKED"):
            continue

        category   = str(row.get("Category",  "")).strip()
        test_name  = str(row.get("Test Name", "")).strip()
        sub_item   = str(row.get("Sub Item",  "")).strip()
        value_str  = str(row.get("Value",     "")).strip()
        hex_id_raw = str(row.get("Hex ID",    "")).strip()

        # Normalise hex_id: "0x45" → "45" (uppercase)
        hex_id = re.sub(r"^0[xX]", "", hex_id_raw).upper() if hex_id_raw else ""

        parsed     = _parse_value(value_str)
        root_cause = _classify_root_cause(result, parsed, category)

        # Override Unknown → No Response for CAN-related failures with no response logs
        if root_cause == "Unknown" and idx["no_response"] and "CAN" in category.upper():
            root_cause = "No Response"

        # --- Log evidence -------------------------------------------------
        log_evidence = ""

        if root_cause == "Blocked":
            log_evidence = idx["blocked_proc"][0] if idx["blocked_proc"] else ""

        elif root_cause == "No Response":
            log_evidence = idx["no_response"][0] if idx["no_response"] else ""

        elif hex_id and hex_id in idx["fail_msgs"]:
            log_evidence = idx["fail_msgs"][hex_id]

        # Retry annotation for CAN items
        if "CAN" in category.upper() or "CAN" in test_name.upper():
            for ch, cnt in idx["retry"].items():
                ch_norm  = re.sub(r"[\-\s]", "", ch).upper()
                nm_norm  = re.sub(r"[\-\s]", "", test_name).upper()
                sub_norm = re.sub(r"[\-\s]", "", sub_item).upper()
                if ch_norm in nm_norm or ch_norm in sub_norm:
                    prefix = f"Retried {cnt}×; "
                    log_evidence = prefix + log_evidence

        # --- Format actual / limit ----------------------------------------
        actual    = ""
        limit_str = ""
        deviation = _format_deviation(parsed)

        if parsed["type"] == "range":
            actual    = f"{parsed['min_val']:.1f} ~ {parsed['max_val']:.1f}"
            limit_str = f"{parsed['lo_limit']:.1f} ~ {parsed['hi_limit']:.1f}"
        elif parsed["type"] == "avg_limit":
            actual    = f"Avg: {parsed['avg_val']:.2f}"
            limit_str = f"{parsed['lo_limit']:.1f} ~ {parsed['hi_limit']:.1f}"
        elif parsed["type"] == "compare":
            actual    = str(parsed["cur_val"])
            limit_str = f"Exp: {parsed['exp_val']}"

        # Supplement actual from UDP Data log if CSV value is missing
        if not actual and hex_id and hex_id in idx["udp"]:
            u = idx["udp"][hex_id]
            if "cur" in u:
                actual = f"Cur:{u['cur']} Avg:{u['avg']} Min:{u['min']} Max:{u['max']}"
            elif "raw" in u:
                actual = f"Raw: {u['raw']}"

        rows.append({
            "Test ID":      row.get("Test ID"),
            "Category":     category,
            "Test Name":    test_name,
            "Sub Item":     sub_item,
            "Root Cause":   root_cause,
            "Actual":       actual,
            "Limit":        limit_str,
            "Deviation":    deviation,
            "Log Evidence": log_evidence,
        })

    return pd.DataFrame(rows)
