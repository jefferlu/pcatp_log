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

from components.sidebar import render_sidebar
from db.database import list_sessions, delete_session
from db.importer import import_session

render_sidebar(show_loop_selector=False)

st.title("Import Sessions")

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

    overwrite = st.checkbox("Overwrite if session already exists", value=False)

    if st.button("Import", type="primary", disabled=not uploaded):
        results = []
        with tempfile.TemporaryDirectory() as tmp_root:
            tmp_path = Path(tmp_root)

            zip_files  = [f for f in uploaded if f.name.endswith(".zip")]
            csv_files  = [f for f in uploaded if f.name.endswith(".csv")]

            # --- Process ZIP files ---
            for zf in zip_files:
                with zipfile.ZipFile(io.BytesIO(zf.read())) as z:
                    z.extractall(tmp_path)

            # --- Process loose CSV files ---
            if csv_files:
                # Detect session_id from filename pattern: test_<ts>.csv or N_EMM_test_<ts>.csv
                session_id = None
                for cf in csv_files:
                    name = cf.name
                    if name.startswith("test_") and "_EMM_" not in name:
                        session_id = name.replace(".csv", "")
                        break
                if session_id is None and csv_files:
                    import re
                    m = re.search(r"(test_\d+)", csv_files[0].name)
                    session_id = m.group(1) if m else "uploaded_session"

                sess_dir = tmp_path / session_id
                sess_dir.mkdir(exist_ok=True)
                for cf in csv_files:
                    (sess_dir / cf.name).write_bytes(cf.read())

            # Discover session directories in tmp_path
            session_dirs = [
                p for p in tmp_path.iterdir()
                if p.is_dir() and p.name.startswith("test_")
            ]
            # Also check one level deeper (ZIP with nested folder)
            if not session_dirs:
                for sub in tmp_path.iterdir():
                    if sub.is_dir():
                        session_dirs += [
                            p for p in sub.iterdir()
                            if p.is_dir() and p.name.startswith("test_")
                        ]

            if not session_dirs:
                st.error("No session folders (test_*) found in uploaded files.")
            else:
                progress = st.progress(0)
                for i, sess_dir in enumerate(session_dirs):
                    with st.spinner(f"Importing {sess_dir.name}…"):
                        result = import_session(sess_dir, overwrite=overwrite)
                        results.append(result)
                    progress.progress((i + 1) / len(session_dirs))

                for r in results:
                    if r["skipped"]:
                        st.warning(
                            f"**{r['session_id']}** — already exists (enable overwrite to replace)."
                        )
                    else:
                        st.success(
                            f"**{r['session_id']}** — imported {r['loops_imported']} loop(s)."
                        )
                st.cache_data.clear()

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
