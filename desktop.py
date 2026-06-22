"""OPLedger desktop entry point (native build).

Runs the FastAPI app with an embedded uvicorn server and shows it in the native
OS webview (WKWebView on macOS, WebView2 on Windows, WebKitGTK on Linux) via
pywebview — no browser dependency, no container, no Podman. Closing the window
stops the server and quits. This is what PyInstaller bundles into the native app.

The same backend powers the self-hosted web service; this file is just the
desktop shell around it.
"""
from __future__ import annotations

import os
import platform
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

# Windowed PyInstaller build (console=False): Windows starts the process with no
# console, so sys.stdout / sys.stderr are None. Several libraries (uvicorn's log
# formatter among them) call sys.stdout.isatty() unconditionally, which raises
# "AttributeError: 'NoneType' object has no attribute 'isatty'" and crashes the
# app before the window opens. Give them real, inert streams when they're missing.
# (When stdout is a real pipe, e.g. the --server-only smoke test, these are
# already non-None and we leave them alone.)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")


def _data_dir() -> Path:
    """Per-user data directory for the encrypted DB + config tree."""
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "OPLedger"
    elif system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OPLedger"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "OPLedger"
    return base


def _free_port() -> int:
    """Grab an ephemeral localhost port (avoids fixed-port conflicts)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except Exception:
            time.sleep(0.3)
    return False


def main() -> int:
    os.environ.setdefault("OPLEDGER_DATA_DIR", str(_data_dir()))

    # Real import (not a string) so PyInstaller bundles the whole backend tree.
    # Must follow the OPLEDGER_DATA_DIR setdefault (config reads it at import).
    import uvicorn
    from backend.main import app

    port = int(os.environ.get("OPLEDGER_PORT") or _free_port())
    url = f"http://127.0.0.1:{port}"

    # Headless mode for smoke-testing the bundle (no window): just run the server.
    if "--server-only" in sys.argv:
        sys.stdout.write(f"OPLEDGER_SERVER_PORT={port}\n")
        sys.stdout.flush()
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
        return 0

    # Embedded server on a background thread; the webview owns the main thread.
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    if not _wait_until(f"{url}/api/setup/status"):
        sys.stderr.write("OPLedger backend failed to start.\n")
        server.should_exit = True
        return 1

    import webview

    webview.create_window("OPLedger", url, width=1200, height=860, min_size=(900, 640))
    webview.start()  # blocks until the window is closed

    # Window closed → stop the server and quit.
    server.should_exit = True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
