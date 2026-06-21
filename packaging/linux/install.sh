#!/usr/bin/env bash
#
# OPLedger Linux installer (native app — no container, no Podman).
#
#   curl -fsSL https://raw.githubusercontent.com/opieeipo/OPLedger/main/packaging/linux/install.sh | bash
#
# Downloads the latest native build, installs it under ~/.local/opt, links the
# `opledger` command, and registers a desktop entry. The app renders in the
# system WebKitGTK webview, so libwebkit2gtk must be present.
#
set -euo pipefail

REPO="opieeipo/OPLedger"
PREFIX="${PREFIX:-$HOME/.local}"
OPT_DIR="$PREFIX/opt/opledger"
BIN_DIR="$PREFIX/bin"
APP_DIR="$PREFIX/share/applications"
ICON_DIR="$PREFIX/share/icons"

echo "Finding the latest OPLedger release ..."
ASSET_URL=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
  | grep -o "https://github.com/${REPO}/releases/download/[^\"]*linux-x86_64.tar.gz" | head -1)
if [ -z "$ASSET_URL" ]; then
  echo "Could not find a Linux build in the latest release." >&2
  exit 1
fi

echo "Downloading $(basename "$ASSET_URL") ..."
TMP=$(mktemp -d)
curl -fsSL "$ASSET_URL" -o "$TMP/opledger.tar.gz"

echo "Installing to $OPT_DIR ..."
rm -rf "$OPT_DIR"
mkdir -p "$OPT_DIR" "$BIN_DIR" "$APP_DIR" "$ICON_DIR"
tar -xzf "$TMP/opledger.tar.gz" -C "$TMP"
cp -R "$TMP/opledger/." "$OPT_DIR/"
ln -sf "$OPT_DIR/opledger" "$BIN_DIR/opledger"
curl -fsSL "https://raw.githubusercontent.com/${REPO}/main/assets/icon.jpeg" -o "$ICON_DIR/opledger.jpeg" 2>/dev/null || true
rm -rf "$TMP"

cat > "$APP_DIR/opledger.desktop" <<EOF
[Desktop Entry]
Name=OPLedger
Comment=Self-hosted, private bookkeeping
Exec=$OPT_DIR/opledger
Icon=$ICON_DIR/opledger.jpeg
Terminal=false
Type=Application
Categories=Office;Finance;
EOF
update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true

echo
echo "OPLedger installed. Run 'opledger' or launch it from your application grid."
# Runtime webview dependency check (varies by distro).
if ! ldconfig -p 2>/dev/null | grep -q "libwebkit2gtk"; then
  echo "  ⚠ WebKitGTK not found — install it so the app window can render, e.g.:"
  echo "      Debian/Ubuntu: sudo apt install gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0"
  echo "      Fedora:        sudo dnf install webkit2gtk4.1"
fi
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "  ⚠ Add $BIN_DIR to your PATH, or run $OPT_DIR/opledger directly." ;; esac
