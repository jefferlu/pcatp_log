"""
Upload Page — Import ATP log sessions into the database.
Select all files from a session directory to import.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

if not st.session_state.get("_username"):
    st.stop()

from components.sidebar import render_sidebar
from db.database import list_sessions, delete_session, import_spec_mapping, get_spec_mapping, build_session_zip
from db.importer import import_session
from parsers.csv_parser import _is_loop_csv

render_sidebar(show_loop_selector=False)

st.markdown("""
<style>
[data-testid="stFileUploaderDropzone"] button { display: none !important; }
</style>
""", unsafe_allow_html=True)

# Counter that increments after every import — changing the key forces
# Streamlit to recreate file_uploader widgets with empty state.
if "_upload_gen" not in st.session_state:
    st.session_state["_upload_gen"] = 0
_gen = st.session_state["_upload_gen"]


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
# Upload Log Files
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Upload Log Files")
    st.caption(
        "Open your session folder, select **all files** (Ctrl+A / Cmd+A), then click Open. "
        "All selected files are treated as one session and imported automatically."
    )
    dir_files = st.file_uploader(
        "Select all files from a session directory",
        type=["csv", "txt"],
        accept_multiple_files=True,
        key=f"dir_upload_{_gen}",
    )
    st.warning("Sessions with the same name will be overwritten automatically.")

    _, btn_col_dir = st.columns([8.8, 1.2])
    _dir_importing = st.session_state.get("_dir_importing", False)
    if btn_col_dir.button("Import", type="primary",
                          disabled=not dir_files or _dir_importing, key=f"import_dir_{_gen}",
                          use_container_width=True):
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
    st.session_state["_upload_gen"] += 1
    st.cache_data.clear()
    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Spec Mapping
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Spec Mapping")
    st.caption("Upload **A.xlsx** to build the test_name → Pin No / Voltage / Load Resistor / EVO IMM Group mapping table.")

    try:
        _mapping_df = get_spec_mapping()
    except Exception:
        _mapping_df = pd.DataFrame()
    if not _mapping_df.empty:
        _counts = _mapping_df.groupby("log_type").size().to_dict()
        _count_str = " &nbsp;|&nbsp; ".join(f"**{lt}**: {n}" for lt, n in sorted(_counts.items()))
        st.success(f"Mapping loaded — {_count_str}")

    _spec_log_type = st.radio(
        "Log type for this file",
        ["Cabin", "Front"],
        horizontal=True,
        key="spec_log_type",
    )

    spec_file = st.file_uploader("Upload A.xlsx", type=["xlsx"], key="spec_upload")
    if spec_file is not None:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as _tmp:
            _tmp.write(spec_file.read())
            _tmp_path = _tmp.name
        with st.spinner("Importing spec mapping…"):
            try:
                _count = import_spec_mapping(_tmp_path, log_type=_spec_log_type)
                st.success(f"Imported **{_count}** mapping entries for **{_spec_log_type}**.")
                st.rerun()
            except Exception as _e:
                st.error(f"Import failed: {_e}")
            finally:
                Path(_tmp_path).unlink(missing_ok=True)

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

    @st.cache_data(show_spinner=False)
    def _cached_build_zip(session_id: str) -> bytes:
        return build_session_zip(session_id)

    for sess in filtered_sessions:
        col_info, col_dl, col_del = st.columns([5, 1, 1])
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
        with col_dl:
            zip_bytes = _cached_build_zip(sess["session_id"])
            st.download_button(
                "Download",
                data=zip_bytes,
                file_name=f"{sess['session_id']}.zip",
                mime="application/zip",
                key=f"dl_{sess['session_id']}",
                use_container_width=True,
            )
        with col_del:
            can_delete = _is_admin or sess.get("owner") == _username
            if can_delete and st.button("Delete", key=f"del_{sess['session_id']}"):
                delete_session(sess["session_id"], username=_username, is_admin=_is_admin)
                st.cache_data.clear()
                st.rerun()
