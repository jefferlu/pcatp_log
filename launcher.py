"""
PyInstaller entry point for ATP Log Analyzer.
Starts the Streamlit server and opens the browser automatically.
"""
import os
import socket
import sys
import threading
import time
import webbrowser


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _resource_path(relative: str) -> str:
    """Return absolute path — works both in dev and when frozen by PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def _open_browser(port: int) -> None:
    time.sleep(3)
    webbrowser.open(f"http://localhost:{port}")


def main() -> None:
    port = _find_free_port()

    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()

    sys.argv = [
        "streamlit",
        "run",
        _resource_path("app.py"),
        "--global.developmentMode=false",
        f"--server.port={port}",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--client.toolbarMode=minimal",
    ]

    from streamlit.web import cli as stcli
    stcli.main()


if __name__ == "__main__":
    main()
