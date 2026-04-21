"""
DuckDB database layer for ATP Log Analyzer.
"""
from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

import duckdb
import pandas as pd

# Priority: ATP_DATA_DIR env var (Docker) > PyInstaller bundle > project root (dev)
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).parent
elif os.environ.get("ATP_DATA_DIR"):
    _BASE_DIR = Path(os.environ["ATP_DATA_DIR"])
else:
    _BASE_DIR = Path(__file__).parent.parent

DB_PATH = _BASE_DIR / "atp_log.duckdb"

_DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id   TEXT PRIMARY KEY,
        owner        TEXT DEFAULT '',
        imported_at  TIMESTAMP DEFAULT current_timestamp,
        test_mode    TEXT,
        total_loops  INTEGER,
        log_type     TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS loop_headers (
        session_id  TEXT,
        loop_num    INTEGER,
        end_time    TEXT,
        test_mode   TEXT,
        PRIMARY KEY (session_id, loop_num)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS results (
        session_id  TEXT,
        loop_num    INTEGER,
        test_id     INTEGER,
        category    TEXT,
        test_name   TEXT,
        sub_item    TEXT,
        result      TEXT,
        value       TEXT,
        hex_id      TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS legacy_results (
        session_id  TEXT,
        loop_num    INTEGER,
        test_id     INTEGER,
        category    TEXT,
        test_name   TEXT,
        sub_item    TEXT,
        result      TEXT,
        value       TEXT,
        hex_id      TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS log_entries (
        session_id  TEXT,
        loop_num    INTEGER,
        time_str    TEXT,
        module      TEXT,
        message     TEXT,
        level       TEXT
    )
    """,
    # Migration: add owner column to existing installations
    """
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS owner TEXT DEFAULT ''
    """,
    # Migration: add log_type column to existing installations
    """
    ALTER TABLE sessions ADD COLUMN IF NOT EXISTS log_type TEXT DEFAULT ''
    """,
    """
    CREATE TABLE IF NOT EXISTS spec_mapping (
        log_type        TEXT,
        test_name       TEXT,
        pin_no          TEXT,
        item_no         TEXT,
        voltage_v       DOUBLE,
        load_resistor   DOUBLE,
        evo_imm_group   TEXT,
        gen1_net_name   TEXT,
        evo_net_name    TEXT,
        PRIMARY KEY (log_type, test_name)
    )
    """,
    # Migration: add log_type to existing spec_mapping that lacks it
    """
    ALTER TABLE spec_mapping ADD COLUMN IF NOT EXISTS log_type TEXT DEFAULT ''
    """,
    # Migration: rename reserved-word column 'no' to 'item_no'
    """
    ALTER TABLE spec_mapping RENAME COLUMN "no" TO item_no
    """,
]

_COL_RENAME = {
    "test_id":   "Test ID",
    "category":  "Category",
    "test_name": "Test Name",
    "sub_item":  "Sub Item",
    "result":    "Result",
    "value":     "Value",
    "hex_id":    "Hex ID",
}


@contextlib.contextmanager
def connect():
    """Open a DuckDB connection, ensure schema exists, yield, then close."""
    conn = duckdb.connect(str(DB_PATH))
    try:
        # Migration: drop spec_mapping if it has the old single-column PK (test_name only).
        # This is safe because spec_mapping data is always re-importable from xlsx.
        try:
            pk_row = conn.execute(
                "SELECT constraint_column_names FROM duckdb_constraints() "
                "WHERE table_name = 'spec_mapping' AND constraint_type = 'PRIMARY KEY'"
            ).fetchone()
            if pk_row and list(pk_row[0]) == ["test_name"]:
                conn.execute("DROP TABLE spec_mapping")
        except Exception:
            pass

        for stmt in _DDL_STATEMENTS:
            try:
                conn.execute(stmt)
            except Exception:
                pass
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Session listing  (access-controlled)
# ---------------------------------------------------------------------------

def list_sessions(username: str, is_admin: bool = False) -> list[dict]:
    """Return sessions visible to *username*.

    Admin sees all sessions. Regular users see only sessions they own.
    """
    with connect() as conn:
        if is_admin:
            rows = conn.execute(
                "SELECT session_id, owner, imported_at, test_mode, total_loops, log_type "
                "FROM sessions ORDER BY imported_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT session_id, owner, imported_at, test_mode, total_loops, log_type "
                "FROM sessions WHERE owner = ? "
                "ORDER BY imported_at DESC",
                [username],
            ).fetchall()
    return [
        {
            "session_id":  r[0],
            "owner":       r[1],
            "imported_at": r[2],
            "test_mode":   r[3],
            "total_loops": r[4],
            "log_type":    r[5] or "",
        }
        for r in rows
    ]


def session_exists(session_id: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", [session_id]
        ).fetchone()
    return row is not None


def get_session_owner(session_id: str) -> str:
    with connect() as conn:
        row = conn.execute(
            "SELECT owner FROM sessions WHERE session_id = ?", [session_id]
        ).fetchone()
    return row[0] if row else ""


def delete_session(session_id: str, username: str, is_admin: bool = False) -> bool:
    """Delete a session. Returns True if deleted, False if permission denied."""
    owner = get_session_owner(session_id)
    if not is_admin and owner != username:
        return False
    with connect() as conn:
        for table in ("sessions", "loop_headers", "results", "legacy_results", "log_entries"):
            conn.execute(f"DELETE FROM {table} WHERE session_id = ?", [session_id])
    return True


# ---------------------------------------------------------------------------
# Load session (same dict format as csv_parser.load_session)
# ---------------------------------------------------------------------------

def load_session(session_id: str) -> dict | None:
    """Load a session from DB, returning the same dict structure as csv_parser.load_session."""
    with connect() as conn:
        sess_row = conn.execute(
            "SELECT test_mode, total_loops FROM sessions WHERE session_id = ?",
            [session_id],
        ).fetchone()
        if sess_row is None:
            return None
        test_mode, total_loops = sess_row

        loop_rows = conn.execute(
            "SELECT loop_num, end_time, test_mode FROM loop_headers "
            "WHERE session_id = ? ORDER BY loop_num",
            [session_id],
        ).fetchall()

        loops: dict = {}
        for loop_num, end_time, loop_mode in loop_rows:
            res_df = conn.execute(
                "SELECT test_id, category, test_name, sub_item, result, value, hex_id "
                "FROM results WHERE session_id = ? AND loop_num = ?",
                [session_id, loop_num],
            ).df().rename(columns=_COL_RENAME)

            leg_df = conn.execute(
                "SELECT test_id, category, test_name, sub_item, result, value, hex_id "
                "FROM legacy_results WHERE session_id = ? AND loop_num = ?",
                [session_id, loop_num],
            ).df().rename(columns=_COL_RENAME)

            loops[loop_num] = {
                "header": {
                    "Test End Time": end_time or "—",
                    "Test Mode":     loop_mode or test_mode or "—",
                },
                "results": res_df,
                "legacy":  leg_df,
            }

    return {
        "id":          session_id,
        "summary":     pd.DataFrame(),
        "loops":       loops,
        "header_meta": {"Test Mode": test_mode or "—"},
    }


def delete_sessions_by_owner(username: str) -> int:
    """Delete all sessions (and related data) owned by *username*.

    Returns the number of sessions deleted.
    """
    with connect() as conn:
        rows = conn.execute(
            "SELECT session_id FROM sessions WHERE owner = ?", [username]
        ).fetchall()
        session_ids = [r[0] for r in rows]
        for sid in session_ids:
            for table in ("sessions", "loop_headers", "results", "legacy_results", "log_entries"):
                conn.execute(f"DELETE FROM {table} WHERE session_id = ?", [sid])
    return len(session_ids)


def load_fail_values(session_ids: list[str]) -> pd.DataFrame:
    """Return all FAIL rows with parsed numeric values for the given sessions.

    Returns a DataFrame with columns:
        session_id, loop_num, test_name, sub_item, param,
        numeric_value, limit_min, limit_max
    Only rows where a numeric value can be extracted from the Value field are included.
    """
    import re
    if not session_ids:
        return pd.DataFrame()

    placeholders = ", ".join("?" * len(session_ids))
    with connect() as conn:
        df = conn.execute(
            f"SELECT session_id, loop_num, test_name, sub_item, value "
            f"FROM results "
            f"WHERE session_id IN ({placeholders}) AND upper(result) = 'FAIL'",
            session_ids,
        ).df()

    if df.empty:
        return pd.DataFrame()

    _avg_re   = re.compile(r"Avg:([\d.Ee+\-]+)")
    _num_re   = re.compile(r"^[\d.Ee+\-]+$")
    _limit_re = re.compile(r"Limit\[([\d.Ee+\-]+)~([\d.Ee+\-]+)\]")

    def _extract_value(val: str) -> float | None:
        try:
            m = _avg_re.search(val)
            if m:
                return float(m.group(1))
            v = val.split("|")[0].strip()
            if _num_re.match(v):
                return float(v)
        except (ValueError, TypeError):
            pass
        return None

    def _extract_limits(val: str) -> tuple[float | None, float | None]:
        try:
            m = _limit_re.search(val)
            if m:
                return float(m.group(1)), float(m.group(2))
        except (ValueError, TypeError):
            pass
        return None, None

    df["numeric_value"] = df["value"].apply(lambda v: _extract_value(str(v)))
    df = df.dropna(subset=["numeric_value"]).copy()
    _limits = df["value"].apply(lambda v: _extract_limits(str(v)))
    df["limit_min"] = _limits.apply(lambda t: t[0])
    df["limit_max"] = _limits.apply(lambda t: t[1])
    sub  = df["sub_item"].astype(str).str.strip()
    name = df["test_name"].astype(str).str.strip()
    df["param"] = sub.where(sub != "", name)
    return df[["session_id", "loop_num", "test_name", "sub_item", "param",
               "numeric_value", "limit_min", "limit_max"]].reset_index(drop=True)


def import_spec_mapping(xlsx_path: str, log_type: str) -> int:
    """Load spec mapping from an xlsx file into the spec_mapping table.

    The matching key (test_name) is built as:
        {Gen1 Net Name without last _XXXX segment}_{EVO Net Name}
    e.g. Gen1=ODH_43_2314, EVO=HSD_H5_5 → test_name=ODH_43_HSD_H5_5

    log_type: "Cabin" or "Front" — used to distinguish mapping sets.
    Returns the number of rows inserted.
    """
    import openpyxl

    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb.active

    rows = []
    for row in ws.iter_rows(min_row=4, values_only=True):
        no       = row[1]
        pin_no   = row[3]
        evo      = row[4]
        gen1     = row[5]
        voltage  = row[6]
        load_res = row[7]
        imm_grp  = row[13]

        if not gen1 or not evo:
            continue

        parts = str(gen1).split("_")
        if len(parts) < 2:
            continue
        prefix = "_".join(parts[:-1])
        test_name_key = f"{prefix}_{evo}"

        rows.append((
            log_type,
            test_name_key,
            str(pin_no).strip().replace("\n", " ") if pin_no  is not None else "",
            str(no)      if no      is not None else "",
            float(voltage)  if voltage  is not None else None,
            float(load_res) if load_res is not None else None,
            str(imm_grp) if imm_grp is not None else "",
            str(gen1),
            str(evo),
        ))

    if not rows:
        return 0

    # Deduplicate: keep first occurrence of each (log_type, test_name)
    seen: set = set()
    deduped = []
    for r in rows:
        key = (r[0], r[1])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    rows = deduped

    with connect() as conn:
        conn.execute("DELETE FROM spec_mapping WHERE log_type = ?", [log_type])
        conn.executemany(
            "INSERT INTO spec_mapping "
            "(log_type, test_name, pin_no, item_no, voltage_v, load_resistor, evo_imm_group, gen1_net_name, evo_net_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def get_spec_mapping(log_type: str | None = None) -> pd.DataFrame:
    """Return spec_mapping rows. Optionally filter by log_type."""
    with connect() as conn:
        if log_type:
            return conn.execute(
                "SELECT log_type, test_name, pin_no, item_no, voltage_v, load_resistor, evo_imm_group, "
                "gen1_net_name, evo_net_name FROM spec_mapping WHERE log_type = ? ORDER BY test_name",
                [log_type],
            ).df()
        return conn.execute(
            "SELECT log_type, test_name, pin_no, item_no, voltage_v, load_resistor, evo_imm_group, "
            "gen1_net_name, evo_net_name FROM spec_mapping ORDER BY log_type, test_name"
        ).df()


def load_all_results(session_ids: list[str]) -> pd.DataFrame:
    """Return all result rows for the given sessions (all results, not just FAIL)."""
    if not session_ids:
        return pd.DataFrame()
    placeholders = ", ".join("?" * len(session_ids))
    with connect() as conn:
        df = conn.execute(
            f"SELECT session_id, loop_num, test_name, sub_item, result, value "
            f"FROM results "
            f"WHERE session_id IN ({placeholders}) "
            f"ORDER BY session_id, loop_num, test_name, sub_item",
            session_ids,
        ).df()
    return df


def load_log_entries(session_id: str, loop_num: int) -> list[dict]:
    """Load log entries for a specific loop."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT time_str, module, message, level FROM log_entries "
            "WHERE session_id = ? AND loop_num = ? ORDER BY rowid",
            [session_id, loop_num],
        ).fetchall()
    return [
        {"time": r[0], "module": r[1], "message": r[2], "level": r[3], "loop": loop_num}
        for r in rows
    ]
