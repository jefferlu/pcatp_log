"""
Parsers for ATP CSV log files.

File types handled:
  - test_<timestamp>.csv          : session summary (no results, only test list)
  - <N>_EMM_test_<timestamp>.csv  : per-loop results (PASS/FAIL/BLOCK + values)
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_header(path: Path) -> dict:
    """Extract the 8-line header block from an ATP CSV file."""
    header = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= 8:
                break
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and parts[0]:
                header[parts[0]] = parts[1]
    return header


def _find_data_start(path: Path) -> int:
    """Return the 0-based line index of the first 'Test ID,...' header row."""
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if line.startswith("Test ID,"):
                return i
    return 9  # fallback


def _parse_csv_table(path: Path, skiprows: int) -> pd.DataFrame:
    """Parse the tabular section starting at *skiprows*.

    The ATP CSV files have a 6-column header row but 7-column data rows
    (the last column is the Hex ID).  We read the header row manually and
    then read the data rows with an extra column appended.
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    if skiprows >= len(lines):
        return pd.DataFrame()

    # The header row
    header_cols = [c.strip() for c in lines[skiprows].split(",")]
    # Append a placeholder for the extra Hex ID column if needed
    if len(header_cols) < 7:
        header_cols.append("Hex ID")

    # Data rows (everything after the header)
    data_lines = lines[skiprows + 1 :]

    rows = []
    for line in data_lines:
        line = line.rstrip("\n\r")
        if not line.strip():
            continue
        parts = line.split(",")
        # Pad short rows, truncate long rows to match header width
        while len(parts) < len(header_cols):
            parts.append("")
        rows.append(parts[: len(header_cols)])

    if not rows:
        return pd.DataFrame(columns=header_cols)

    df = pd.DataFrame(rows, columns=header_cols)
    df = df.dropna(how="all")
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_session_summary(session_dir: Path) -> pd.DataFrame:
    """
    Parse the master summary CSV (``test_<ts>.csv``).

    Returns a DataFrame with columns:
        Test ID, Category, Test Name, Sub Item, Hex ID
    (No Result/Value — this file is only the test item list.)
    """
    session_id = session_dir.name
    csv_path = session_dir / f"{session_id}.csv"
    if not csv_path.exists():
        return pd.DataFrame()

    skip = _find_data_start(csv_path)
    df = _parse_csv_table(csv_path, skip)

    # The summary CSV has 7 columns: Test ID,Category,Test Name,Sub Item,Result,Value,[Hex]
    # Result & Value are empty; last column is Hex ID
    df = df[df["Test ID"].notna() & df["Test ID"].str.match(r"^\d+$", na=False)]
    df["Test ID"] = df["Test ID"].astype(int)

    # Last column is Hex ID (unnamed in some files)
    unnamed = [c for c in df.columns if c.startswith("Unnamed")]
    if unnamed:
        df = df.rename(columns={unnamed[-1]: "Hex ID"})

    return df.reset_index(drop=True)


def parse_loop_results(loop_csv: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """
    Parse a per-loop CSV file (``<N>_EMM_test_<ts>.csv``).

    Returns:
        header  : dict  with Test Mode, Test Loop, Test End Time, Total Tests, etc.
        main_df : DataFrame of the primary test items (Test ID 1-100)
        legacy_df: DataFrame of the appended legacy rows (CAN/LIN/etc.)
    """
    if not loop_csv.exists():
        return {}, pd.DataFrame(), pd.DataFrame()

    header = _read_header(loop_csv)

    # Find the two 'Test ID,' header rows
    header_lines = []
    with open(loop_csv, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if line.startswith("Test ID,"):
                header_lines.append(i)

    if not header_lines:
        return header, pd.DataFrame(), pd.DataFrame()

    # --- Primary table ---
    main_df = _parse_csv_table(loop_csv, header_lines[0])
    # Keep only rows with numeric Test ID
    main_df = main_df[main_df["Test ID"].str.match(r"^\d+$", na=False)].copy()
    main_df["Test ID"] = main_df["Test ID"].astype(int)

    # Drop rows that are separators / headers
    main_df = main_df[main_df["Test ID"] > 0]

    # Split at the legacy separator if present
    legacy_df = pd.DataFrame()
    if len(header_lines) >= 2:
        legacy_df = _parse_csv_table(loop_csv, header_lines[1])
        legacy_df = legacy_df[
            legacy_df["Test ID"].str.match(r"^\d+$", na=False)
        ].copy()
        legacy_df["Test ID"] = legacy_df["Test ID"].astype(int)

        # main_df should only contain rows before the separator
        # Re-read limited to between the two header rows
        main_df = _parse_csv_table(loop_csv, header_lines[0])
        main_df = main_df.iloc[: header_lines[1] - header_lines[0] - 1]
        main_df = main_df[main_df["Test ID"].str.match(r"^\d+$", na=False)].copy()
        main_df["Test ID"] = main_df["Test ID"].astype(int)
        main_df = main_df[main_df["Test ID"] > 0]

    # Normalise Result column
    if "Result" in main_df.columns:
        main_df["Result"] = main_df["Result"].fillna("").str.strip()

    # Last non-standard column = Hex ID
    unnamed = [c for c in main_df.columns if c.startswith("Unnamed")]
    if unnamed:
        main_df = main_df.rename(columns={unnamed[-1]: "Hex ID"})

    return header, main_df.reset_index(drop=True), legacy_df.reset_index(drop=True)


def load_session(session_dir: Path) -> dict:
    """
    Load an entire test session from a directory.

    Returns::

        {
            "id":      str,
            "summary": DataFrame,      # master test list
            "loops":   {
                1: {"header": dict, "results": DataFrame, "legacy": DataFrame},
                ...
            },
            "header_meta": dict,       # from first loop header
        }
    """
    session_dir = Path(session_dir)
    session_id = session_dir.name

    data: dict = {
        "id": session_id,
        "summary": parse_session_summary(session_dir),
        "loops": {},
        "header_meta": {},
    }

    # Discover loop CSV files
    loop_pattern = re.compile(rf"^(\d+)_EMM_{re.escape(session_id)}\.csv$")
    loop_files = sorted(
        session_dir.glob("*_EMM_*.csv"),
        key=lambda p: int(loop_pattern.match(p.name).group(1))
        if loop_pattern.match(p.name)
        else 9999,
    )

    for lf in loop_files:
        m = loop_pattern.match(lf.name)
        if not m:
            continue
        loop_num = int(m.group(1))
        header, results, legacy = parse_loop_results(lf)
        data["loops"][loop_num] = {
            "header": header,
            "results": results,
            "legacy": legacy,
        }
        if not data["header_meta"] and header:
            data["header_meta"] = header

    return data
