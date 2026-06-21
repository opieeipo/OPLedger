# Packaging & distribution

OPLedger ships as a **Podman container** plus a thin **launcher** that runs the
container and opens it in a chromeless Google Chrome window (closing the window
stops the container). Three install channels wrap that same launcher.

```
packaging/
├── launcher/opledger        # macOS/Linux launcher (container + Chrome app window)
├── launcher/opledger.ps1    # Windows launcher
├── homebrew/opledger.rb     # Homebrew formula (→ tap repo)
├── scoop/opledger.json      # Scoop manifest (→ bucket repo)
└── linux/install.sh         # curl | bash installer
.github/workflows/release.yml # build+push image, create release on a v* tag
```

Everything targets the **`opieeipo`** identity:
- Image: `ghcr.io/opieeipo/opledger`
- Tap: `opieeipo/homebrew-opledger`
- Bucket: `opieeipo/scoop-opledger`
- Linux installer served from raw GitHub on `opieeipo/OPLedger`

## Dependencies (all channels)
- **Podman** — the container runtime (declared as a dependency by brew/scoop;
  the Linux installer and launcher warn if missing).
- **Google Chrome** — required for the app window (`--app` mode). Chromium works
  as a fallback for the launcher.

## Cutting a release
1. Bump the version in `backend/main.py`, `homebrew/opledger.rb`,
   `scoop/opledger.json`, and tag: `git tag v0.1.0 && git push --tags`.
2. CI (`release.yml`) builds the Containerfile, pushes
   `ghcr.io/opieeipo/opledger:{latest,v0.1.0}`, and creates the GitHub Release.
   Make the GHCR package **public** once (Settings → Packages) so users can pull.
3. Compute checksums against the auto-generated source archives and paste them
   into the formula/manifest:
   ```sh
   V=0.1.0
   curl -fsSL https://github.com/opieeipo/OPLedger/archive/refs/tags/v$V.tar.gz | shasum -a 256   # → homebrew sha256
   curl -fsSL https://github.com/opieeipo/OPLedger/archive/refs/tags/v$V.zip    | shasum -a 256   # → scoop hash
   ```

## Publishing each channel

**Homebrew** — create repo `opieeipo/homebrew-opledger`, put this formula at
`Formula/opledger.rb`. Install:
```sh
brew tap opieeipo/opledger
brew install opledger
brew install --cask google-chrome
opledger
```

**Scoop** — create repo `opieeipo/scoop-opledger`, put `opledger.json` at its
root (or in `bucket/`). Install:
```powershell
scoop bucket add opledger https://github.com/opieeipo/scoop-opledger
scoop install opledger
opledger
```

**Linux** — the installer is served straight from the repo:
```sh
curl -fsSL https://raw.githubusercontent.com/opieeipo/OPLedger/main/packaging/linux/install.sh | bash
```

## Notes
- The README's published instructions use an `opledger` org; these artifacts use
  `opieeipo` to match the actual remote. If you later create the `opledger` org,
  change the identifiers here and in `release.yml` + the README.
- The tap and bucket are separate Git repos; the canonical copies of the formula
  and manifest live here so they're versioned with the app.
