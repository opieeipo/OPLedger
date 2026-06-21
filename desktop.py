"""OPLedger desktop entry point (native build).

Runs the FastAPI app with an embedded uvicorn server and opens it in a chromeless
Google Chrome window — no browser chrome, its own Dock/taskbar entry. Closing the
window stops the server and quits. This is what PyInstaller bundles into the
native app; there is no container and no Podman dependency.

Google Chrome is required (Chromium accepted as a fallback).
"""
from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


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


def _find_chrome() -> str | None:
    candidates = []
    system = platform.system()
    if system == "Darwin":
        candidates += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif system == "Windows":
        for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            root = os.environ.get(env)
            if root:
                candidates.append(str(Path(root) / "Google/Chrome/Application/chrome.exe"))
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def _wait_until(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except Exception:
            time.sleep(0.3)
    return False


def _window_open(devtools_port: int, port: int) -> bool:
    """True while the app's DevTools page target exists (window still open)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{devtools_port}/json", timeout=2) as r:
            return f"127.0.0.1:{port}".encode() in r.read()
    except Exception:
        return False


def main() -> int:
    os.environ.setdefault("OPLEDGER_DATA_DIR", str(_data_dir()))

    # Real import (not a string) so PyInstaller bundles the whole backend tree.
    # Must follow the OPLEDGER_DATA_DIR setdefault above (config reads it at import).
    import uvicorn
    from backend.main import app

    # Headless mode for smoke-testing the bundle (no Chrome): just run the server.
    if "--server-only" in sys.argv:
        port = int(os.environ.get("OPLEDGER_PORT") or _free_port())
        sys.stdout.write(f"OPLEDGER_SERVER_PORT={port}\n")
        sys.stdout.flush()
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
        return 0

    chrome = _find_chrome()
    if not chrome:
        sys.stderr.write(
            "OPLedger requires Google Chrome, which was not found.\n"
            "Install it from https://www.google.com/chrome/ and try again.\n"
        )
        return 1

    port = int(os.environ.get("OPLEDGER_PORT") or _free_port())
    url = f"http://127.0.0.1:{port}"
    devtools_port = int(os.environ.get("OPLEDGER_DEVTOOLS_PORT") or _free_port())
    profile_dir = os.environ.get("OPLEDGER_PROFILE_DIR") or str(Path.home() / ".opledger" / "chrome-profile")

    # Embedded server on a background thread.
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not _wait_until(f"{url}/api/setup/status"):
        sys.stderr.write("OPLedger backend failed to start.\n")
        server.should_exit = True
        return 1

    # Open the chromeless app window.
    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [chrome, f"--app={url}", f"--user-data-dir={profile_dir}",
         f"--remote-debugging-port={devtools_port}", "--class=OPLedger",
         "--no-first-run", "--no-default-browser-check", "--window-size=1200,860"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # Watch the window via DevTools (Chrome can outlive its window, esp. on macOS).
    appeared = False
    for _ in range(30):
        if _window_open(devtools_port, port):
            appeared = True
            break
        time.sleep(0.5)
    if appeared:
        while _window_open(devtools_port, port):
            time.sleep(1)
    else:
        proc.wait()

    # Window closed → tear down.
    proc.terminate()
    server.should_exit = True
    thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
