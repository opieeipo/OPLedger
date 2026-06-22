# Faithful smoke test for the Windows desktop build.
#
# The native build ships as a GUI-subsystem exe (opledger.spec: console=False).
# When a user launches it, Windows attaches no console, so Python sets
# sys.stdout / sys.stderr to None. Libraries that call sys.stdout.isatty()
# (uvicorn's log formatter among them) then crash at startup with the "Unable to
# configure formatter 'default'" failure reported in issue #2.
#
# To reproduce that condition we must launch the built exe DETACHED, with NO
# stdout redirect (redirecting hands it a real stream and hides the bug). We run
# it headless via --server-only on a pinned port (so we don't need stdout to
# discover the port) and probe the HTTP endpoint: if the build crashes at
# startup the server never binds and the probe times out; if it's healthy the
# endpoint answers.
#
# Usage:
#   # 1. Build in a CLEAN venv (the global Python may carry stale deps):
#   python -m venv .venv-build
#   .\.venv-build\Scripts\python -m pip install -r requirements-desktop.txt
#   .\.venv-build\Scripts\pyinstaller --noconfirm opledger.spec
#   # 2. Smoke test the artifact the way a user runs it:
#   powershell -ExecutionPolicy Bypass -File scripts\smoke-windows.ps1
param(
  [string]$ExePath = "dist\opledger\opledger.exe",
  [int]$TimeoutSec = 40,
  [int]$Port = 8137
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path $ExePath)) {
  Write-Error "Not found: $ExePath. Build it first (see header of this script)."
  exit 2
}

$env:OPLEDGER_PORT = "$Port"
$DataDir = Join-Path $env:TEMP ("opledger-smoke-" + [guid]::NewGuid().ToString("N"))
$env:OPLEDGER_DATA_DIR = $DataDir
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

Write-Host "Launching $ExePath --server-only on :$Port (detached, no stdout)..."
# No -RedirectStandardOutput: the exe must see sys.stdout == None, exactly as
# when a user double-clicks it. That is the whole point of this test.
$proc = Start-Process -FilePath $ExePath -ArgumentList "--server-only" -PassThru

$url = "http://127.0.0.1:$Port/api/setup/status"
$ok = $false
for ($i = 0; $i -lt ($TimeoutSec * 2); $i++) {
  if ($proc.HasExited) {
    Write-Host "Process exited early (code $($proc.ExitCode)) -- startup crash."
    break
  }
  try {
    Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 1 | Out-Null
    $ok = $true
    break
  } catch {
    Start-Sleep -Milliseconds 500
  }
}

if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
Remove-Item -Recurse -Force $DataDir -ErrorAction SilentlyContinue

if ($ok) {
  Write-Host "SMOKE PASS: backend answered on :$Port -- no startup/formatter crash."
  exit 0
} else {
  Write-Error "SMOKE FAIL: backend never answered within $TimeoutSec sec -- the windowed build likely crashed at startup (see issue #2)."
  exit 1
}
