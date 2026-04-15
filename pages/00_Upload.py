"""
Upload Page — Import ATP log sessions into the database.
Supports ZIP archives, individual CSV files, or selecting directories from the client.
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


# ---------------------------------------------------------------------------
# Show import results carried over from the previous run (after st.rerun)
# ---------------------------------------------------------------------------
if "_import_results" in st.session_state:
    for r in st.session_state.pop("_import_results"):
        if r.get("error"):
            st.error(r["error"])
        else:
            log_type_tag = f" `{r['log_type']}`" if r.get("log_type") else ""
            skipped = r.get("loops_skipped", [])
            if skipped:
                skipped_nums = ", ".join(str(s["loop"]) for s in skipped)
                st.warning(
                    f"**{r['session_id']}**{log_type_tag} — "
                    f"imported {r['loops_imported']} loop(s), "
                    f"skipped {len(skipped)} loop(s) (missing TXT): loop {skipped_nums}."
                )
            else:
                st.success(
                    f"**{r['session_id']}**{log_type_tag} — imported {r['loops_imported']} loop(s)."
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
# Import from Directory
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Import from Directory")
    st.caption(
        "Open your session folder, select **all files** (Ctrl+A / Cmd+A), then click Open. "
        "All selected files are treated as one session and imported automatically."
    )

    dir_files = st.file_uploader(
        "Select all files from a session directory",
        type=["csv", "txt"],
        accept_multiple_files=True,
        key="dir_upload",
    )

    _, btn_col_dir = st.columns([8, 1])
    _dir_importing = st.session_state.get("_dir_importing", False)
    if btn_col_dir.button("Import", type="primary",
                          disabled=not dir_files or _dir_importing, key="import_dir"):
        st.session_state["_dir_importing"] = True
        st.rerun()

if st.session_state.get("_dir_importing") and dir_files:
    results = []
    with tempfile.TemporaryDirectory() as tmp_root:
        tmp_path = Path(tmp_root)
        with st.spinner("Packing & importing…"):
            try:
                staging = tmp_path / "_staging"
                staging.mkdir()
                for uf in dir_files:
                    (staging / uf.name).write_bytes(uf.read())

                def _session_from_loop_stem(stem: str) -> str:
                    parts = stem.split("_")
                    if len(parts) > 2 and parts[0].isdigit():
                        return "_".join(parts[2:])
                    return stem

                session_id = None
                for p in sorted(staging.glob("*.csv")):
                    is_loop, _ = _is_loop_csv(p)
                    if is_loop:
                        session_id = _session_from_loop_stem(p.stem)
                        break
                if session_id is None:
                    for p in sorted(staging.glob("*.csv")):
                        session_id = p.stem
                        break
                if session_id is None:
                    session_id = Path(dir_files[0].name).stem

                zip_buf = io.BytesIO()
                zip_buf.name = f"{session_id}.zip"
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for f in sorted(staging.iterdir()):
                        if f.is_file():
                            zf.write(f, f.name)
                zip_buf.seek(0)

                dirs = _prepare_zip_sessions(zip_buf, tmp_path)
                if not dirs:
                    results.append({
                        "session_id": session_id, "loops_imported": 0,
                        "loops_skipped": [], "skipped": False,
                        "error": f"**{session_id}** — no CSV files found.",
                    })
                else:
                    for sess_dir in dirs:
                        owner = st.session_state.get("_username", "")
                        result = import_session(sess_dir, overwrite=True, owner=owner)
                        results.append(result)
            except Exception as e:
                results.append({
                    "session_id": "", "loops_imported": 0,
                    "loops_skipped": [], "skipped": False,
                    "error": f"Import failed: {e}",
                })
    st.session_state["_dir_importing"] = False
    st.session_state["_import_results"] = results
    st.cache_data.clear()
    st.rerun()

st.divider()

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

    st.warning("Sessions with the same name will be overwritten automatically.")

    _, btn_col = st.columns([8, 1])
    _uploading = st.session_state.get("_uploading", False)
    if btn_col.button("Import", type="primary",
                      disabled=not uploaded or _uploading, use_container_width=True):
        st.session_state["_uploading"] = True
        st.rerun()

if st.session_state.get("_uploading") and uploaded:
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
                        result = import_session(sess_dir, overwrite=True, owner=owner)
                    except Exception as e:
                        result = {
                            "session_id": sess_dir.name,
                            "loops_imported": 0,
                            "skipped": False,
                            "error": f"**{sess_dir.name}** — import failed: {e}",
                        }
                    results.append(result)
                progress.progress((i + 1) / len(session_dirs))

    st.session_state["_uploading"] = False
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
    _available_types = sorted({s["log_type"] for s in sessions if s.get("log_type")})
    if len(_available_types) >= 2:
        _filter_options = ["All"] + _available_types
        _selected_filter = st.radio(
            "Filter by type",
            _filter_options,
            horizontal=True,
            key="upload_type_filter",
        )
        filtered_sessions = (
            sessions if _selected_filter == "All"
            else [s for s in sessions if s.get("log_type") == _selected_filter]
        )
    else:
        filtered_sessions = sessions

    for sess in filtered_sessions:
        col_info, col_del = st.columns([5, 1])
        with col_info:
            owner_tag = f" &nbsp;|&nbsp; Owner: `{sess['owner']}`" if _is_admin and sess.get("owner") else ""
            type_tag = f" &nbsp;|&nbsp; Type: `{sess['log_type']}`" if sess.get("log_type") else ""
            st.markdown(
                f"**{sess['session_id']}**"
                + type_tag
                + f" &nbsp;|&nbsp; Mode: `{sess['test_mode'] or '—'}`"
                f" &nbsp;|&nbsp; Loops: **{sess['total_loops']}**"
                + owner_tag
            )
        with col_del:
            can_delete = _is_admin or sess.get("owner") == _username
            if can_delete and st.button("Delete", key=f"del_{sess['session_id']}"):
                delete_session(sess["session_id"], username=_username, is_admin=_is_admin)
                st.cache_data.clear()
                st.rerun()
