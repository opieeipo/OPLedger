#!/usr/bin/env bash
#
# OPLedger desktop launcher (macOS / Linux).
#
# Opens OPLedger in a chromeless Google Chrome window — no address bar, no
# tabs, its own Dock/taskbar entry — so it looks and behaves like a native
# desktop app even though it's an HTML/CSS/JS app served locally. Closing the
# window shuts the backend down with it.
#
# Google Chrome is a REQUIRED dependency. The app-window experience relies on
# Chrome's --app mode, so we target Chrome specifically rather than trying to
# work across every browser. (Chromium is accepted as a drop-in fallback.)
#
# Usage:
#   scripts/opledger-app.sh          # production: runs the container (compose)
#   scripts/opledger-app.sh --dev    # development: runs uvicorn from .venv
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${OPLEDGER_PORT:-8080}"
[[ "${1:-}" == "--dev" ]] && DEV=1 && PORT="${OPLEDGER_PORT:-8099}" || DEV=0
URL="http://127.0.0.1:${PORT}"

# A dedicated Chrome profile keeps OPLedger isolated from your everyday Chrome
# (so this launch is its own process we can wait on) and persists your login
# between launches, the way a real app would.
PROFILE_DIR="${OPLEDGER_PROFILE_DIR:-$HOME/.opledger/chrome-profile}"

# --- locate Google Chrome ------------------------------------------------
find_chrome() {
  local c
  for c in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    google-chrome google-chrome-stable chromium chromium-browser
  do
    if [[ -x "$c" ]]; then printf '%s\n' "$c"; return 0; fi
    if command -v "$c" >/dev/null 2>&1; then command -v "$c"; return 0; fi
  done
  return 1
}

if ! CHROME="$(find_chrome)"; then
  echo "OPLedger requires Google Chrome, which was not found." >&2
  echo "Install it from https://www.google.com/chrome/ and run this again." >&2
  exit 1
fi

# --- single-instance guard ----------------------------------------------
# The teardown below relies on the Chrome launch blocking until the window
# closes. If a Chrome is already running on this profile, a new --app launch
# hands the window off to it and returns immediately — which would tear the
# backend down while the window is still open. Refuse rather than misfire.
if pgrep -f -- "--user-data-dir=$PROFILE_DIR" >/dev/null 2>&1; then
  echo "OPLedger already appears to be open. Close that window first." >&2
  exit 1
fi

# --- start the backend ---------------------------------------------------
if [[ "$DEV" == "1" ]]; then
  echo "Starting OPLedger (dev — uvicorn, autoreload) on ${URL} ..."
  OPLEDGER_DATA_DIR="${OPLEDGER_DATA_DIR:-$ROOT/.localdata}" \
    "$ROOT/.venv/bin/uvicorn" backend.main:app --host 127.0.0.1 --port "$PORT" \
      --reload --reload-dir "$ROOT/backend" &
  BACKEND_PID=$!
  stop_backend() {
    kill "$BACKEND_PID" 2>/dev/null || true
    # --reload spawns a worker child; reap anything still bound to our port.
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | xargs -r kill 2>/dev/null || true
  }
else
  echo "Starting OPLedger on ${URL} ..."
  ( cd "$ROOT" && podman-compose -f compose.yaml up -d )
  stop_backend() { ( cd "$ROOT" && podman-compose -f compose.yaml down ); }
fi

# Tear the backend down no matter how we exit (window close, Ctrl-C, error).
trap stop_backend EXIT INT TERM

# --- wait for the server to answer --------------------------------------
for _ in $(seq 1 60); do
  curl -fsS "${URL}/api/setup/status" >/dev/null 2>&1 && break
  sleep 0.5
done

# --- open the app window -------------------------------------------------
# On macOS, Chrome's --app process often keeps running after its window closes,
# so we can't just wait for the process to exit. Instead we open a private
# DevTools port and watch for the app's page target: it disappears the moment
# the window closes — even if the Chrome process lingers — and that's our signal
# to tear everything down.
mkdir -p "$PROFILE_DIR"
DEVTOOLS_PORT="${OPLEDGER_DEVTOOLS_PORT:-$((PORT + 1000))}"

echo "OPLedger is open. Close the window to quit."
"$CHROME" \
  --app="$URL" \
  --user-data-dir="$PROFILE_DIR" \
  --remote-debugging-port="$DEVTOOLS_PORT" \
  --class="OPLedger" \
  --no-first-run \
  --no-default-browser-check \
  --window-size=1180,860 \
  >/dev/null 2>&1 &
CHROME_PID=$!

# Is the app window's page target still open?
window_open() {
  curl -fsS "http://127.0.0.1:${DEVTOOLS_PORT}/json" 2>/dev/null | grep -q "127.0.0.1:${PORT}"
}

# Wait for the window to appear (~15s), then watch until it closes.
appeared=0
for _ in $(seq 1 30); do if window_open; then appeared=1; break; fi; sleep 0.5; done
if [[ "$appeared" == "1" ]]; then
  while window_open; do sleep 1; done
else
  # DevTools never answered; fall back to waiting on the process.
  wait "$CHROME_PID" 2>/dev/null || true
fi

# Window closed → quit the (possibly lingering) Chrome, then the EXIT trap
# stops the backend.
kill "$CHROME_PID" 2>/dev/null || true
pkill -f -- "--user-data-dir=$PROFILE_DIR" 2>/dev/null || true
