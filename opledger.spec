# OPLedger PyInstaller spec — native desktop build (no container, no Podman).
# Build:  pyinstaller --noconfirm opledger.spec
#   macOS   → dist/OPLedger.app   Windows/Linux → dist/opledger/ (onedir)
import os
import sys

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

_icon = "assets/icon.icns" if os.path.exists("assets/icon.icns") else None

hidden = []
hidden += collect_submodules("uvicorn")          # uvicorn loads protocols/lifespan dynamically
hidden += collect_submodules("backend")          # full backend tree (imported app object)
hidden += collect_submodules("ofxparse")
hidden += collect_submodules("webview")          # pywebview + its OS webview backend

datas = [("frontend", "frontend"), ("assets", "assets"), ("config", "config")]
datas += collect_data_files("reportlab")          # PDF fonts/data

a = Analysis(
    ["desktop.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="opledger",
    console=False,            # GUI app — the UI is the Chrome window, no terminal
    icon=_icon,
    target_arch=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="opledger")

# On macOS, wrap the onedir into a proper .app bundle (the cask installs this).
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="OPLedger.app",
        icon=_icon,
        bundle_identifier="io.github.opieeipo.opledger",
        info_plist={
            "CFBundleName": "OPLedger",
            "CFBundleDisplayName": "OPLedger",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
        },
    )
