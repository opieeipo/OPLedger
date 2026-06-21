# Packaging & distribution

OPLedger ships two ways from **one codebase**:

- **Native desktop app** (macOS / Windows / Linux) — a PyInstaller bundle that
  runs the backend in-process and renders in the OS webview (`pywebview`). No
  container, no browser dependency. Built by `opledger.spec`.
- **Self-hosted web service** — the same backend as a container (`Containerfile`
  + `compose.yaml`, image `ghcr.io/opieeipo/opledger`) that users reach in a
  browser.

```
opledger.spec                 # PyInstaller build (→ .app / onedir)
desktop.py                    # native entry: embedded uvicorn + OS webview
requirements-desktop.txt      # backend deps + pywebview + pyinstaller
packaging/
├── homebrew/Casks/opledger.rb  # macOS cask (→ tap repo)
├── scoop/opledger.json         # Scoop manifest (→ bucket repo, bucket/)
└── linux/install.sh            # curl | bash installer (native tarball)
.github/workflows/release.yml   # on v* tag: image + native matrix + release
```

All targets use `opieeipo`: image `ghcr.io/opieeipo/opledger`, tap
`opieeipo/homebrew-opledger`, bucket `opieeipo/scoop-opledger`.

## Cutting a release
1. Bump `version` in `backend/main.py`, the cask, and the Scoop manifest; tag:
   `git tag v0.2.0 && git push --tags`.
2. CI builds the container image **and** the native apps (macOS `.app` zip,
   Windows zip, Linux tar.gz), then publishes a GitHub Release with all of them
   attached. Make the GHCR package public once (it's only needed for the
   self-host image, not the desktop apps).
3. Fill checksums from the release assets and push to the tap/bucket repos:
   ```sh
   V=0.2.0
   for a in macOS-arm64.zip windows-x64.zip; do
     curl -fsSL "https://github.com/opieeipo/OPLedger/releases/download/v$V/OPLedger-v$V-$a" | shasum -a 256
   done
   ```
   → cask `sha256` (macOS), Scoop `hash` (Windows). The Linux installer reads the
   latest release via the API, so it needs no checksum baked in.

## Publishing each channel
- **Homebrew** — repo `opieeipo/homebrew-opledger`, cask at `Casks/opledger.rb`.
  Install: `brew install --cask opieeipo/opledger/opledger`.
- **Scoop** — repo `opieeipo/scoop-opledger`, manifest at `bucket/opledger.json`.
  Install: `scoop bucket add opledger https://github.com/opieeipo/scoop-opledger && scoop install opledger`.
- **Linux** — served from this repo:
  `curl -fsSL https://raw.githubusercontent.com/opieeipo/OPLedger/main/packaging/linux/install.sh | bash`.

## macOS signing
`release.yml` signs + notarizes when the Apple secrets are set
(`MACOS_CERT_P12`, `MACOS_CERT_PASSWORD`, `MACOS_SIGN_IDENTITY`, `APPLE_ID`,
`APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` — same names as Stash). Absent → ships
unsigned (Gatekeeper right-click-Open the first time).

## Per-OS runtime notes
- **Windows:** needs the Edge **WebView2** runtime (preinstalled on Win11 / most Win10).
- **Linux:** needs **WebKitGTK** (`libwebkit2gtk`); the installer warns if missing.
- **macOS:** uses the built-in WKWebView — no extra runtime.
