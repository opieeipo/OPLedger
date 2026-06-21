# OPLedger desktop launcher (Windows).
#
# Opens OPLedger in a chromeless Google Chrome window — no address bar, no
# tabs, its own taskbar entry — so it looks and behaves like a native desktop
# app even though it's an HTML/CSS/JS app served locally. Closing the window
# shuts the backend down with it.
#
# Google Chrome is a REQUIRED dependency. The app-window experience relies on
# Chrome's --app mode, so we target Chrome specifically rather than trying to
# work across every browser.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\opledger-app.ps1          # production (container)
#   powershell -ExecutionPolicy Bypass -File scripts\opledger-app.ps1 -Dev     # development (uvicorn)
param([switch]$Dev)
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if ($Dev) {
  $Port = if ($env:OPLEDGER_PORT) { $env:OPLEDGER_PORT } else { "8099" }
} else {
  $Port = if ($env:OPLEDGER_PORT) { $env:OPLEDGER_PORT } else { "8080" }
}
$Url = "http://127.0.0.1:$Port"

# Dedicated Chrome profile: isolates OPLedger from your everyday Chrome and
# persists your login between launches, the way a real app would.
$ProfileDir = if ($env:OPLEDGER_PROFILE_DIR) { $env:OPLEDGER_PROFILE_DIR } `
              else { Join-Path $env:LOCALAPPDATA "OPLedger\chrome-profile" }

# --- locate Google Chrome ------------------------------------------------
$Chrome = @(
  (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
  (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
  (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Chrome) {
  Write-Error "OPLedger requires Google Chrome. Install it from https://www.google.com/chrome/ and run this again."
  exit 1
}

# --- single-instance guard ----------------------------------------------
# Start-Process -Wait below relies on launching our own Chrome process. If one
# is already running on this profile, the new --app launch hands off and returns
# at once, tearing the backend down while the window is still open. Refuse.
$already = Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape("--user-data-dir=$ProfileDir") }
if ($already) {
  Write-Error "OPLedger already appears to be open. Close that window first."
  exit 1
}

# --- start the backend ---------------------------------------------------
Push-Location $Root
try {
  if ($Dev) {
    Write-Host "Starting OPLedger (dev - uvicorn) on $Url ..."
    if (-not $env:OPLEDGER_DATA_DIR) { $env:OPLEDGER_DATA_DIR = (Join-Path $Root ".localdata") }
    $backend = Start-Process -FilePath (Join-Path $Root ".venv\Scripts\uvicorn.exe") `
      -ArgumentList @("backend.main:app", "--host", "127.0.0.1", "--port", $Port) `
      -PassThru -NoNewWindow
  } else {
    Write-Host "Starting OPLedger on $Url ..."
    podman-compose -f compose.yaml up -d
  }

  # --- wait for the server to answer -------------------------------------
  for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest -UseBasicParsing "$Url/api/setup/status" -TimeoutSec 1 | Out-Null; break }
    catch { Start-Sleep -Milliseconds 500 }
  }

  # --- open the app window ----------------------------------------------
  # Don't rely on the Chrome process exiting on window close (it can linger).
  # Open a private DevTools port and watch for the app's page target: it
  # disappears the moment the window closes, and that's our teardown signal.
  New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null
  $DevPort = if ($env:OPLEDGER_DEVTOOLS_PORT) { [int]$env:OPLEDGER_DEVTOOLS_PORT } else { [int]$Port + 1000 }

  Write-Host "OPLedger is open. Close the window to quit."
  $chromeProc = Start-Process -FilePath $Chrome -PassThru -ArgumentList @(
    "--app=$Url",
    "--user-data-dir=$ProfileDir",
    "--remote-debugging-port=$DevPort",
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1180,860"
  )

  function Test-WindowOpen {
    try {
      $j = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$DevPort/json" -TimeoutSec 2
      return ($j.Content -match "127.0.0.1:$Port")
    } catch { return $false }
  }

  $appeared = $false
  for ($i = 0; $i -lt 30; $i++) { if (Test-WindowOpen) { $appeared = $true; break }; Start-Sleep -Milliseconds 500 }
  if ($appeared) {
    while (Test-WindowOpen) { Start-Sleep -Seconds 1 }
  } else {
    $chromeProc.WaitForExit()
  }

  # Window closed → quit any lingering Chrome on this profile.
  Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape("--user-data-dir=$ProfileDir") } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
finally {
  # Window closed (or error) → stop the backend.
  if ($Dev) {
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
  } else {
    podman-compose -f compose.yaml down
  }
  Pop-Location
}
