#!/usr/bin/env bash
#
# OPLedger Linux installer.
#
#   curl -fsSL https://raw.githubusercontent.com/opieeipo/OPLedger/main/packaging/linux/install.sh | bash
#
# Installs the `opledger` launcher to ~/.local/bin and registers a desktop
# entry. OPLedger runs as a Podman container and opens in Google Chrome, so it
# checks for both and points you at install instructions if they're missing.
#
set -euo pipefail

REPO="opieeipo/OPLedger"
REF="${OPLEDGER_REF:-main}"
RAW="https://raw.githubusercontent.com/${REPO}/${REF}"
PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
APP_DIR="$PREFIX/share/applications"
ICON_DIR="$PREFIX/share/icons"

echo "Installing OPLedger ..."
mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

# Launcher
curl -fsSL "$RAW/packaging/launcher/opledger" -o "$BIN_DIR/opledger"
chmod +x "$BIN_DIR/opledger"

# Icon
curl -fsSL "$RAW/assets/icon.jpeg" -o "$ICON_DIR/opledger.jpeg" 2>/dev/null || true

# Desktop entry (absolute Exec — desktop launchers don't use the shell PATH)
cat > "$APP_DIR/opledger.desktop" <<EOF
[Desktop Entry]
Name=OPLedger
Comment=Self-hosted, private bookkeeping
Exec=$BIN_DIR/opledger
Icon=$ICON_DIR/opledger.jpeg
Terminal=false
Type=Application
Categories=Office;Finance;
EOF

update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true

echo
echo "OPLedger installed to $BIN_DIR/opledger"

# Dependency checks (warn, don't fail — package managers vary by distro).
command -v podman >/dev/null 2>&1 || \
  echo "  ⚠ Podman not found — install it, e.g.: sudo apt install podman  (or dnf/pacman/zypper)"
if ! command -v google-chrome >/dev/null 2>&1 && ! command -v google-chrome-stable >/dev/null 2>&1 \
   && ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
  echo "  ⚠ Google Chrome not found — install Chrome (or Chromium) to launch the app window."
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "  ⚠ $BIN_DIR is not on your PATH — add it, or run $BIN_DIR/opledger directly." ;;
esac

echo
echo "Run 'opledger' or launch OPLedger from your application grid."
