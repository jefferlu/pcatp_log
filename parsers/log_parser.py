"""
Parser for ATP TestSetResponse.txt log files.

Format:
    [HH:MM:SS] [MODULE] message
    or
    === Test Start (Loop N): YYYY-MM-DD HH:MM:SS ===
"""
from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime


# Regex patterns
_LINE_RE = re.compile(
    r"^\[(\d{2}:\d{2}:\d{2})\]\s+\[([^\]]+)\]\s+(.*)$"
)
_START_RE = re.compile(
    r"^=== Test Start(?:\s+\(Loop\s+(\d+)\))?\s*:\s*([\d\-: ]+)\s*===$"
)


def extract_loop_number(txt_path: Path) -> int | None:
    """Read the first 15 lines of a per-loop TXT to find its loop number.

    Checks two sources (whichever appears first):
    - ``=== Test Start (Loop N) ===``  (first line)
    - ``[Info ] Loop Number   = N``    (within the info block)

    Returns None if the TXT is a master session log (no loop number found).
    """
    _start_re = re.compile(r"^=== Test Start\s+\(Loop\s+(\d+)\)", re.IGNORECASE)
    _num_re   = re.compile(r"Loop Number\s*=\s*(\d+)", re.IGNORECASE)
    try:
        with open(txt_path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= 15:
                    break
                for pattern in (_start_re, _num_re):
                    m = pattern.search(line)
                    if m:
                        return int(m.group(1))
    except OSError:
        pass
    return None


def extract_project_name(txt_path: Path) -> str:
    """Read the first 20 lines of a per-loop TXT to find 'Project Name = ...'

    Returns the project name (e.g. 'Front', 'Cabin') or empty string if not found.
    """
    _proj_re = re.compile(r"Project Name\s*=\s*(\S+)", re.IGNORECASE)
    try:
        with open(txt_path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= 20:
                    break
                m = _proj_re.search(line)
                if m:
                    return m.group(1).strip()
    except OSError:
        pass
    return ""


def parse_test_set_response(log_path: Path) -> list[dict]:
    """
    Parse a TestSetResponse.txt file into a list of log entries.

    Each entry is a dict::

        {
            "time":    str,        # "HH:MM:SS"
            "module":  str,        # e.g. "MQTT", "CAN", "FAIL"
            "message": str,
            "level":   str,        # "info" | "warning" | "error" | "pass" | "fail"
            "loop":    int | None, # loop number if parseable from context
        }
    """
    log_path = Path(log_path)
    if not log_path.exists():
        return []

    entries: list[dict] = []
    current_loop: int | None = None

    with open(log_path, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip()

            # Check for section header
            m_start = _START_RE.match(line)
            if m_start:
                loop_str = m_start.group(1)
                current_loop = int(loop_str) if loop_str else None
                entries.append({
                    "time": "",
                    "module": "System",
                    "message": line,
                    "level": "info",
                    "loop": current_loop,
                })
                continue

            m = _LINE_RE.match(line)
            if not m:
                if line.strip():
                    entries.append({
                        "time": "",
                        "module": "raw",
                        "message": line,
                        "level": "info",
                        "loop": current_loop,
                    })
                continue

            time_str, module, message = m.group(1), m.group(2).strip(), m.group(3)
            level = _classify_level(module, message)

            entries.append({
                "time": time_str,
                "module": module,
                "message": message,
                "level": level,
                "loop": current_loop,
            })

    return entries


def _classify_level(module: str, message: str) -> str:
    mod = module.upper()
    msg = message.upper()

    if mod == "FAIL" or "FAIL" in msg:
        return "fail"
    if "PASS" in msg and "FAIL" not in msg:
        return "pass"
    if mod in ("ERROR", "ERR"):
        return "error"
    if "WARNING" in msg or "WARN" in msg:
        return "warning"
    return "info"


def extract_udp_data(entries: list[dict]) -> list[dict]:
    """
    Extract UDP Data entries from parsed log entries.

    Returns list of dicts::

        {"time", "id", "name", "cur", "avg", "min", "max", "raw"}
    """
    udp_re = re.compile(
        r"ID:([0-9A-Fa-f]+)\s+\(([^)]+)\)\s+\|\s+(.*)"
    )
    numeric_re = re.compile(
        r"Cur:([\d.Ee\-+]+)\s+Avg:([\d.Ee\-+]+)\s+Min:([\d.Ee\-+]+)\s+Max:([\d.Ee\-+]+)"
    )
    raw_re = re.compile(r"RawData:([0-9A-Fa-f\-]+)")

    result = []
    for e in entries:
        if e["module"].strip() != "UDP Data":
            continue
        m = udp_re.search(e["message"])
        if not m:
            continue
        hex_id, name, payload = m.group(1), m.group(2), m.group(3)
        entry = {
            "time": e["time"],
            "id": hex_id,
            "name": name,
            "cur": None, "avg": None, "min": None, "max": None,
            "raw": None,
        }
        mn = numeric_re.search(payload)
        if mn:
            entry["cur"] = float(mn.group(1))
            entry["avg"] = float(mn.group(2))
            entry["min"] = float(mn.group(3))
            entry["max"] = float(mn.group(4))
        mr = raw_re.search(payload)
        if mr:
            entry["raw"] = mr.group(1)
        result.append(entry)
    return result
