"""
Import parsed session data into DuckDB.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from db.database import connect, delete_session, session_exists
from parsers.csv_parser import load_session as parse_session
from parsers.log_parser import parse_test_set_response


def import_session(session_dir: Path, overwrite: bool = False) -> dict:
    """Parse a session directory and import it into DuckDB.

    Returns a status dict: {"session_id", "loops_imported", "skipped": bool}
    """
    session_dir = Path(session_dir)
    session_id = session_dir.name

    if session_exists(session_id):
        if not overwrite:
            return {"session_id": session_id, "loops_imported": 0, "skipped": True}
        delete_session(session_id)

    session_data = parse_session(session_dir)
    loops = session_data.get("loops", {})
    meta = session_data.get("header_meta", {})

    # Pre-parse all .txt files in the directory (sorted), then pair them with
    # loops in sorted order — no filename convention assumed.
    txt_files = sorted(session_dir.glob("*.txt"))
    txt_entries: dict[int, list] = {}
    sorted_loop_nums = sorted(loops.keys())
    for idx, txt_file in enumerate(txt_files):
        if idx >= len(sorted_loop_nums):
            break
        entries = parse_test_set_response(txt_file)
        if entries:
            txt_entries[sorted_loop_nums[idx]] = entries

    with connect() as conn:
        # sessions table
        conn.execute(
            "INSERT INTO sessions (session_id, test_mode, total_loops) VALUES (?, ?, ?)",
            [session_id, meta.get("Test Mode", ""), len(loops)],
        )

        for loop_num, ldata in loops.items():
            header  = ldata.get("header", {})
            res_df  = ldata.get("results", pd.DataFrame())
            leg_df  = ldata.get("legacy",  pd.DataFrame())

            # loop_headers
            conn.execute(
                "INSERT INTO loop_headers (session_id, loop_num, end_time, test_mode) VALUES (?, ?, ?, ?)",
                [session_id, loop_num,
                 header.get("Test End Time", ""),
                 header.get("Test Mode", "")],
            )

            # results
            if not res_df.empty:
                _insert_results(conn, "results", session_id, loop_num, res_df)

            # legacy_results
            if not leg_df.empty:
                _insert_results(conn, "legacy_results", session_id, loop_num, leg_df)

            # log_entries
            entries = txt_entries.get(loop_num, [])
            if entries:
                log_rows = [
                    (session_id, loop_num, e["time"], e["module"], e["message"], e["level"])
                    for e in entries
                ]
                conn.executemany(
                    "INSERT INTO log_entries (session_id, loop_num, time_str, module, message, level) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    log_rows,
                )

    return {"session_id": session_id, "loops_imported": len(loops), "skipped": False}


def _insert_results(conn, table: str, session_id: str, loop_num: int, df: pd.DataFrame) -> None:
    col_map = {
        "Test ID":   "test_id",
        "Category":  "category",
        "Test Name": "test_name",
        "Sub Item":  "sub_item",
        "Result":    "result",
        "Value":     "value",
        "Hex ID":    "hex_id",
    }
    insert_df = pd.DataFrame()
    insert_df["test_id"]   = df.get("Test ID",   pd.Series(dtype="object")).astype(str)
    insert_df["category"]  = df.get("Category",  pd.Series(dtype="object")).fillna("")
    insert_df["test_name"] = df.get("Test Name", pd.Series(dtype="object")).fillna("")
    insert_df["sub_item"]  = df.get("Sub Item",  pd.Series(dtype="object")).fillna("")
    insert_df["result"]    = df.get("Result",    pd.Series(dtype="object")).fillna("")
    insert_df["value"]     = df.get("Value",     pd.Series(dtype="object")).fillna("")
    insert_df["hex_id"]    = df.get("Hex ID",    pd.Series(dtype="object")).fillna("")

    # Convert test_id to int where possible
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
