# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for ATP Log Analyzer.

Build steps (run on Windows):
    pip install pyinstaller
    pyinstaller ATPLogAnalyzer.spec --clean
Output: dist\ATPLogAnalyzer\ATPLogAnalyzer.exe
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files

# ---------------------------------------------------------------------------
# Collect Streamlit's static files and hidden imports
# ---------------------------------------------------------------------------
st_datas, st_binaries, st_hiddenimports = collect_all("streamlit")

# Altair / Vega schemas bundled with streamlit
alt_datas, _, _ = collect_all("altair")

# ---------------------------------------------------------------------------
# Application source files to bundle
# ---------------------------------------------------------------------------
app_datas = [
    ("app.py",              "."),
    ("pages",               "pages"),
    ("components",          "components"),
    ("utils",               "utils"),
    ("parsers",             "parsers"),
    ("db",                  "db"),
    (".streamlit/config.toml", ".streamlit"),
]

all_datas    = app_datas + st_datas + alt_datas
all_binaries = st_binaries

all_hiddenimports = st_hiddenimports + [
    # DuckDB
    "duckdb",
    # Plotly
    "plotly",
    "plotly.express",
    "plotly.graph_objects",
    "plotly.io",
    # Data
    "pandas",
    "pyarrow",
    "pyarrow.vendored.version",
    # Streamlit internals that are dynamically imported
    "streamlit.runtime.scriptrunner.magic_funcs",
    "streamlit.components.v1",
    # Network / async
    "tornado",
    "tornado.platform.asyncio",
    "asyncio",
    # Misc
    "click",
    "validators",
    "packaging",
    "toml",
    "rich",
    "PIL",
    "pydeck",
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "notebook", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ATPLogAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,      # No black console window
    icon=None,          # Replace with "icon.ico" if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ATPLogAnalyzer",
)
