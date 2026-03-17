"""
Shared utility functions for the ATP Log Analyzer.
"""
from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Result colour mapping
# ---------------------------------------------------------------------------

RESULT_COLORS = {
    "PASS":  "#00CC66",   # green
    "FAIL":  "#FF4444",   # red
    "BLOCK": "#FFAA00",   # amber
    "":      "#888888",   # grey (not executed)
}

LOG_LEVEL_COLORS = {
    "fail":    "#FF4444",
    "error":   "#FF6600",
    "warning": "#FFAA00",
    "pass":    "#00CC66",
    "info":    "#AAAAAA",
}


def result_color(result: str) -> str:
    """Return a hex colour string for a given test result."""
    return RESULT_COLORS.get(str(result).strip().upper(), "#888888")


def result_badge(result: str) -> str:
    """Return an HTML badge span for a result string."""
    r = str(result).strip().upper()
    color = result_color(r)
    label = r if r else "—"
    return (
        f'<span style="background:{color};color:#000;padding:2px 8px;'
        f'border-radius:4px;font-weight:bold;font-size:0.85em">{label}</span>'
    )


# ---------------------------------------------------------------------------
# Value cell formatting
# ---------------------------------------------------------------------------

_MINMAX_RE = re.compile(
    r"Min:([\d.]+)\s+Max:([\d.]+)\s+\|\s+Limit\[([0-9.]+)~([0-9.]+)\]"
)
_RAW_RE = re.compile(r"Raw:([0-9A-Fa-f\-]+)")


def format_value_cell(value: str) -> dict:
    """
    Parse a Value cell string and return a structured dict.

    Returns::

        {
            "type":   "range" | "raw" | "raw_exp" | "plain",
            "min":    float | None,
            "max":    float | None,
            "lo":     float | None,
            "hi":     float | None,
            "raw":    str | None,
            "text":   str,          # original text
        }
    """
    if not value or not isinstance(value, str):
        return {"type": "plain", "min": None, "max": None,
                "lo": None, "hi": None, "raw": None, "text": ""}

    m = _MINMAX_RE.search(value)
    if m:
        return {
            "type": "range",
            "min":  float(m.group(1)),
            "max":  float(m.group(2)),
            "lo":   float(m.group(3)),
            "hi":   float(m.group(4)),
            "raw":  None,
            "text": value,
        }

    m = _RAW_RE.search(value)
    if m:
        return {
            "type": "raw",
            "min":  None, "max":  None, "lo":  None, "hi":  None,
            "raw":  m.group(1),
            "text": value,
        }

    return {"type": "plain", "min": None, "max": None,
            "lo": None, "hi": None, "raw": None, "text": value}


# ---------------------------------------------------------------------------
# Session / Loop discovery
# ---------------------------------------------------------------------------

LOG_ROOT = Path(__file__).parent.parent / ".log_files"


def discover_sessions(log_root: Path | None = None) -> list[Path]:
    """
    Return sorted list of session directories under *log_root*.
    Default root is ``<project>/.log_files``.
    """
    root = Path(log_root) if log_root else LOG_ROOT
    if not root.exists():
        return []
    return sorted(
        [p for p in root.iterdir() if p.is_dir() and p.name.startswith("test_")],
        key=lambda p: p.name,
        reverse=True,   # most recent first
    )


def get_loop_numbers(session_data: dict) -> list[int]:
    """Return sorted list of loop numbers from a loaded session dict."""
    return sorted(session_data.get("loops", {}).keys())
