"""
Upload Page — Import ATP log sessions into the database.
Supports ZIP archives or individual CSV files.
"""
from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

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
# Upload section
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Upload Log Files")
    st.caption(
        "Upload a **ZIP** archive containing one or more session folders, "
        "or select multiple **CSV** files from a single session."
    )

    uploaded = st.file_uploader(
        "Choose file(s)",
        type=["zip", "csv"],
        accept_multiple_files=True,
    )

    overwrite = st.checkbox("Overwrite if session already exists", value=True)

    if st.button("Import", type="primary", disabled=not uploaded):
        results = []
        with tempfile.TemporaryDirectory() as tmp_root:
            tmp_path = Path(tmp_root)

            zip_files = [f for f in uploaded if f.name.endswith(".zip")]
            csv_files = [f for f in uploaded if f.name.endswith(".csv")]

            # --- Process ZIP files ---
            for zf in zip_files:
                with zipfile.ZipFile(io.BytesIO(zf.read())) as z:
                    z.extractall(tmp_path)

            # --- Process loose CSV files ---
            if csv_files:
                # Write files to a temp dir, then use content to find the summary CSV
                staging = tmp_path / "_loose_csv_staging"
                staging.mkdir()
                for cf in csv_files:
                    (staging / cf.name).write_bytes(cf.read())

                # Identify session_id from the summary CSV (not a loop CSV)
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

            # Discover ALL subdirectories in tmp_path (no name restriction)
            session_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
            # Also check one level deeper (ZIP with a nested parent folder)
            if not session_dirs:
                for sub in tmp_path.iterdir():
                    if sub.is_dir():
                        session_dirs += [p for p in sub.iterdir() if p.is_dir()]

            if not session_dirs:
                results.append({"error": "No folders found in uploaded files.",
                                "session_id": "", "loops_imported": 0, "skipped": False})
            else:
                progress = st.progress(0)
                for i, sess_dir in enumerate(session_dirs):
                    with st.spinner(f"Importing {sess_dir.name}…"):
                        result = import_session(sess_dir, overwrite=overwrite)
                        results.append(result)
                    progress.progress((i + 1) / len(session_dirs))

        # Store results and rerun so sidebar refreshes with new sessions
        st.session_state["_import_results"] = results
        st.cache_data.clear()
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Imported sessions list
# ---------------------------------------------------------------------------
st.subheader("Imported Sessions")

sessions = list_sessions()
if not sessions:
    st.info("No sessions imported yet.")
else:
    for sess in sessions:
        col_info, col_del = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"**{sess['session_id']}** &nbsp;|&nbsp; "
                f"Mode: `{sess['test_mode'] or '—'}` &nbsp;|&nbsp; "
                f"Loops: **{sess['total_loops']}** &nbsp;|&nbsp; "
                f"Imported: {str(sess['imported_at'])[:19]}"
            )
        with col_del:
            if st.button("Delete", key=f"del_{sess['session_id']}"):
                delete_session(sess["session_id"])
                st.cache_data.clear()
                st.rerun()
