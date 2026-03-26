"""
Import parsed session data into DuckDB.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from db.database import connect, delete_session, session_exists, get_session_owner
from parsers.csv_parser import load_session as parse_session
from parsers.log_parser import parse_test_set_response, extract_project_name, extract_loop_number


def _map_loop_txts(session_dir: Path) -> dict[int, Path]:
    """Return {loop_num: txt_path} by reading the loop number from each TXT's content.

    Per-loop TXT files contain ``=== Test Start (Loop N) ===`` on the first line
    (or ``Loop Number = N`` within the first 15 lines).  The master session TXT
    has no loop number in its content and is therefore excluded automatically.
    """
    mapping: dict[int, Path] = {}
    for txt in session_dir.glob("*.txt"):
        loop_num = extract_loop_number(txt)
        if loop_num is not None:
            mapping[loop_num] = txt
    return mapping


def import_session(session_dir: Path, overwrite: bool = False, owner: str = "") -> dict:
    """Parse a session directory and import it into DuckDB.

    Only loops that have **both** a CSV and a matching per-loop TXT file are
    imported.  Loops missing their TXT are skipped and reported separately so
    that a single missing file never blocks the rest of the session.

    Returns::

        {
            "session_id":     str,
            "loops_imported": int,
            "loops_skipped":  list[{"loop": int, "reason": str}],
            "skipped":        bool,   # True only when the whole session is skipped
            "log_type":       str,    # "Front" | "Cabin" | ""
            "error":          str,    # non-empty on hard failure
        }
    """
    session_dir = Path(session_dir)
    session_id = session_dir.name

    _empty = {"session_id": session_id, "loops_imported": 0,
              "loops_skipped": [], "skipped": False, "log_type": "", "error": ""}

    if session_exists(session_id):
        existing_owner = get_session_owner(session_id)
        if existing_owner:
            owner = existing_owner
        delete_session(session_id, username=owner or "__system__", is_admin=True)

    session_data = parse_session(session_dir)
    loops = session_data.get("loops", {})
    meta = session_data.get("header_meta", {})

    if not loops:
        return {**_empty, "error": f"**{session_id}** — no loop CSV files found."}

    # Map loop_num → per-loop TXT (by numeric filename prefix)
    txt_map = _map_loop_txts(session_dir)

    # Determine log_type from the first available per-loop TXT
    log_type = ""
    for loop_num in sorted(txt_map):
        name = extract_project_name(txt_map[loop_num])
        if name:
            log_type = name
            break

    loops_skipped: list[dict] = []
    complete_loops: list[int] = []

    for loop_num in sorted(loops.keys()):
        if loop_num not in txt_map:
            loops_skipped.append({"loop": loop_num, "reason": "missing TXT file"})
        else:
            complete_loops.append(loop_num)

    if not complete_loops:
        return {
            **_empty,
            "loops_skipped": loops_skipped,
            "error": (
                f"**{session_id}** — no complete loop pairs (CSV + TXT) found. "
                f"{len(loops_skipped)} loop(s) missing TXT."
            ),
        }

    # Pre-parse TXT entries for complete loops only
    txt_entries: dict[int, list] = {}
    for loop_num in complete_loops:
        entries = parse_test_set_response(txt_map[loop_num])
        if entries:
            txt_entries[loop_num] = entries

    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, owner, test_mode, total_loops, log_type) "
            "VALUES (?, ?, ?, ?, ?)",
            [session_id, owner, meta.get("Test Mode", ""), len(complete_loops), log_type],
        )

        for loop_num in complete_loops:
            ldata = loops[loop_num]
            header  = ldata.get("header", {})
            res_df  = ldata.get("results", pd.DataFrame())
            leg_df  = ldata.get("legacy",  pd.DataFrame())

            conn.execute(
                "INSERT INTO loop_headers (session_id, loop_num, end_time, test_mode) "
                "VALUES (?, ?, ?, ?)",
                [session_id, loop_num,
                 header.get("Test End Time", ""),
                 header.get("Test Mode", "")],
            )

            if not res_df.empty:
                _insert_results(conn, "results", session_id, loop_num, res_df)

            if not leg_df.empty:
                _insert_results(conn, "legacy_results", session_id, loop_num, leg_df)

            entries = txt_entries.get(loop_num, [])
            if entries:
                log_rows = [
                    (session_id, loop_num, e["time"], e["module"], e["message"], e["level"])
                    for e in entries
                ]
                conn.executemany(
                    "INSERT INTO log_entries "
                    "(session_id, loop_num, time_str, module, message, level) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    log_rows,
                )

    return {
        "session_id":     session_id,
        "loops_imported": len(complete_loops),
        "loops_skipped":  loops_skipped,
        "skipped":        False,
        "log_type":       log_type,
        "error":          "",
    }


def _insert_results(conn, table: str, session_id: str, loop_num: int, df: pd.DataFrame) -> None:
    insert_df = pd.DataFrame()
    insert_df["test_id"]   = df.get("Test ID",   pd.Series(dtype="object")).astype(str)
    insert_df["category"]  = df.get("Category",  pd.Series(dtype="object")).fillna("")
    insert_df["test_name"] = df.get("Test Name", pd.Series(dtype="object")).fillna("")
    insert_df["sub_item"]  = df.get("Sub Item",  pd.Series(dtype="object")).fillna("")
    insert_df["result"]    = df.get("Result",    pd.Series(dtype="object")).fillna("")
    insert_df["value"]     = df.get("Value",     pd.Series(dtype="object")).fillna("")
    insert_df["hex_id"]    = df.get("Hex ID",    pd.Series(dtype="object")).fillna("")

    try:
        insert_df["test_id"] = insert_df["test_id"].astype(int)
    except (ValueError, TypeError):
        pass

    rows = [
        (session_id, loop_num,
         row["test_id"], row["category"], row["test_name"],
         row["sub_item"], row["result"], row["value"], row["hex_id"])
        for _, row in insert_df.iterrows()
    ]
    conn.executemany(
        f"INSERT INTO {table} "
        "(session_id, loop_num, test_id, category, test_name, sub_item, result, value, hex_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
