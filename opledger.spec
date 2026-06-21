# OPLedger PyInstaller spec — native desktop build (no container, no Podman).
# Build:  pyinstaller --noconfirm opledger.spec   →  dist/opledger/opledger
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hidden = []
hidden += collect_submodules("uvicorn")          # uvicorn loads protocols/lifespan dynamically
hidden += collect_submodules("backend")          # app is referenced by string "backend.main:app"
hidden += collect_submodules("ofxparse")
hidden += ["sqlcipher3", "sqlcipher3.dbapi2"]    # encrypted-DB driver (native extension)

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
    console=True,
    target_arch=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="opledger")
