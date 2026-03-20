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
        total_loops  INTEGER
    )
    """,
    # Grant read access to a session for additional users (beyond the owner)
    """
    CREATE TABLE IF NOT EXISTS session_shares (
        session_id  TEXT,
        username    TEXT,
        PRIMARY KEY (session_id, username)
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
        for stmt in _DDL_STATEMENTS:
            conn.execute(stmt)
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Shares sync  (config/shares.yaml → session_shares table)
# ---------------------------------------------------------------------------

def sync_shares(shares_config: dict) -> None:
    """Sync sharing config into the session_shares table.

    shares_config format (from shares.yaml['shares']):
        { session_id: { owner: str, shared_with: [username, ...] }, ... }
    """
    if not shares_config:
        return

    rows = []
    for session_id, entry in shares_config.items():
        for username in entry.get("shared_with", []):
            rows.append((session_id, username))

    with connect() as conn:
        # Full replace: remove stale entries then insert current config
        conn.execute("DELETE FROM session_shares")
        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO session_shares (session_id, username) VALUES (?, ?)",
                rows,
            )


# ---------------------------------------------------------------------------
# Session listing  (access-controlled)
# ---------------------------------------------------------------------------

def list_sessions(username: str, is_admin: bool = False) -> list[dict]:
    """Return sessions visible to *username*.

    Admin sees all sessions.
    Regular users see sessions they own + sessions shared with them.
    """
    with connect() as conn:
        if is_admin:
            rows = conn.execute(
                "SELECT session_id, owner, imported_at, test_mode, total_loops "
                "FROM sessions ORDER BY imported_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT s.session_id, s.owner, s.imported_at, s.test_mode, s.total_loops "
                "FROM sessions s "
                "WHERE s.owner = ? "
                "   OR s.session_id IN ("
                "       SELECT session_id FROM session_shares WHERE username = ?"
                "   ) "
                "ORDER BY s.imported_at DESC",
                [username, username],
            ).fetchall()
    return [
        {
            "session_id":  r[0],
            "owner":       r[1],
            "imported_at": r[2],
            "test_mode":   r[3],
            "total_loops": r[4],
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
        for table in ("sessions", "loop_headers", "results", "legacy_results",
                      "log_entries", "session_shares"):
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
