"""
Upload Page — Import ATP log sessions into the database.
Supports ZIP archives or individual CSV files.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

if not st.session_state.get("_username"):
    st.stop()

from components.sidebar import render_sidebar
from db.database import list_sessions, delete_session
from db.importer import import_session
from parsers.csv_parser import _is_loop_csv

render_sidebar(show_loop_selector=False)

st.title("Import Sessions")

# ---------------------------------------------------------------------------
# Show import results carried over from the previous run (after st.rerun)
# ---------------------------------------------------------------------------
if "_import_results" in st.session_state:
    for r in st.session_state.pop("_import_results"):
        if r.get("error"):
            st.error(r["error"])
        elif r["skipped"]:
            st.warning(
                f"**{r['session_id']}** — already exists (enable overwrite to replace)."
            )
        else:
            st.success(
                f"**{r['session_id']}** — imported {r['loops_imported']} loop(s)."
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_metadata(path: Path, base: Path) -> bool:
    """True if any path component is an OS-generated metadata dir."""
    return any(
        part.startswith(("__", "."))
        for part in path.relative_to(base).parts
    )


def _collect_files(base: Path, suffix: str) -> list[Path]:
    return [p for p in base.rglob(f"*{suffix}") if not _is_metadata(p, base)]


def _prepare_zip_sessions(zf_file, tmp_path: Path) -> list[Path]:
    """
    Extract one ZIP and return a list of session directories to import.

    Session ID rules:
      - CSVs packed directly into the ZIP (flat) → session ID = ZIP stem
      - CSVs inside a single subfolder → session ID = subfolder name
      - CSVs across multiple subfolders → one session per subfolder, ID = subfolder name
    """
    zip_stem = Path(zf_file.name).stem
    extract_dir = tmp_path / f"_zip_{zip_stem}"
    extract_dir.mkdir()

    with zipfile.ZipFile(io.BytesIO(zf_file.read())) as z:
        z.extractall(extract_dir)

    all_csvs = _collect_files(extract_dir, ".csv")
    all_txts = _collect_files(extract_dir, ".txt")

    if not all_csvs:
        return []

    # Group CSVs by their immediate parent directory
    from collections import defaultdict
    groups: dict[Path, list[Path]] = defaultdict(list)
    for csv in all_csvs:
        groups[csv.parent].append(csv)

    session_dirs: list[Path] = []

    if len(groups) == 1:
        src_dir = next(iter(groups))
        # Flat ZIP (CSVs directly in extract_dir) → use ZIP stem as session ID
        # Single-subfolder ZIP → use subfolder name as session ID
        sess_id = zip_stem if src_dir == extract_dir else src_dir.name
        sess_dir = tmp_path / sess_id
        sess_dir.mkdir(exist_ok=True)
        for f in all_csvs + [t for t in all_txts if t.parent == src_dir]:
            shutil.move(str(f), sess_dir / f.name)
        session_dirs.append(sess_dir)
    else:
        # Multiple directories → one session per directory, named after subfolder
        for src_dir, csvs in sorted(groups.items()):
            sess_id = src_dir.name if src_dir != extract_dir else zip_stem
            sess_dir = tmp_path / sess_id
            sess_dir.mkdir(exist_ok=True)
            txts_here = [t for t in all_txts if t.parent == src_dir]
            for f in csvs + txts_here:
                shutil.move(str(f), sess_dir / f.name)
            session_dirs.append(sess_dir)

    return session_dirs


# ---------------------------------------------------------------------------
# Upload section
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Upload Log Files")
    st.caption(
        "Upload a **ZIP** archive (CSVs directly or inside a folder) "
        "or select multiple **CSV** files from a single session."
    )

    uploaded = st.file_uploader(
        "Choose file(s)",
        type=["zip", "csv"],
        accept_multiple_files=True,
    )

    overwrite = st.checkbox("Overwrite if session already exists", value=True)

    _, btn_col = st.columns([8, 1])
    if btn_col.button("Import", type="primary", disabled=not uploaded, use_container_width=True):
        results = []
        with tempfile.TemporaryDirectory() as tmp_root:
            tmp_path = Path(tmp_root)

            zip_files = [f for f in uploaded if f.name.endswith(".zip")]
            csv_files = [f for f in uploaded if f.name.endswith(".csv")]

            session_dirs: list[Path] = []

            # --- Process ZIP files (each ZIP → one or more sessions) ---
            for zf in zip_files:
                dirs = _prepare_zip_sessions(zf, tmp_path)
                if not dirs:
                    results.append({
                        "error": f"No CSV files found in **{zf.name}**.",
                        "session_id": "", "loops_imported": 0, "skipped": False,
                    })
                else:
                    session_dirs.extend(dirs)

            # --- Process loose CSV files → session named after summary CSV ---
            if csv_files:
                staging = tmp_path / "_staging"
                staging.mkdir()
                for cf in csv_files:
                    (staging / cf.name).write_bytes(cf.read())

                session_id = None
                for p in sorted(staging.glob("*.csv")):
                    is_loop, _ = _is_loop_csv(p)
                    if not is_loop:
                        session_id = p.stem
                        break
                if session_id is None:
                    session_id = Path(csv_files[0].name).stem

                sess_dir = tmp_path / session_id
                sess_dir.mkdir(exist_ok=True)
                for p in staging.iterdir():
                    p.rename(sess_dir / p.name)
                session_dirs.append(sess_dir)

            # --- Import ---
            if session_dirs:
                progress = st.progress(0)
                for i, sess_dir in enumerate(session_dirs):
                    with st.spinner(f"Importing {sess_dir.name}…"):
                        try:
                            owner = st.session_state.get("_username", "")
                            result = import_session(sess_dir, overwrite=overwrite, owner=owner)
                        except Exception as e:
                            result = {
                                "session_id": sess_dir.name,
                                "loops_imported": 0,
                                "skipped": False,
                                "error": f"**{sess_dir.name}** — import failed: {e}",
                            }
                        results.append(result)
                    progress.progress((i + 1) / len(session_dirs))

        st.session_state["_import_results"] = results
        st.cache_data.clear()
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Imported sessions list
# ---------------------------------------------------------------------------
st.subheader("Imported Sessions")

_username = st.session_state.get("_username", "")
_is_admin = st.session_state.get("_is_admin", False)

sessions = list_sessions(_username, is_admin=_is_admin)
if not sessions:
    st.info("No sessions imported yet.")
else:
    for sess in sessions:
        col_info, col_del = st.columns([5, 1])
        with col_info:
            owner_tag = f" &nbsp;|&nbsp; Owner: `{sess['owner']}`" if _is_admin and sess.get("owner") else ""
            st.markdown(
                f"**{sess['session_id']}** &nbsp;|&nbsp; "
                f"Mode: `{sess['test_mode'] or '—'}` &nbsp;|&nbsp; "
                f"Loops: **{sess['total_loops']}** &nbsp;|&nbsp; "
                f"Imported: {str(sess['imported_at'])[:19]}"
                + owner_tag
            )
        with col_del:
            can_delete = _is_admin or sess.get("owner") == _username
            if can_delete and st.button("Delete", key=f"del_{sess['session_id']}"):
                delete_session(sess["session_id"], username=_username, is_admin=_is_admin)
                st.cache_data.clear()
                st.rerun()
