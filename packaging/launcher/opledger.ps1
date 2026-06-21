# OPLedger desktop launcher (installed via Scoop).
#
# Runs the OPLedger container with Podman and opens it in a chromeless Google
# Chrome window. Closing the window stops the container.
#
# Requires: Podman and Google Chrome.
param([switch]$Help)
$ErrorActionPreference = "Stop"

$Image = if ($env:OPLEDGER_IMAGE) { $env:OPLEDGER_IMAGE } else { "ghcr.io/opieeipo/opledger:latest" }
$Port  = if ($env:OPLEDGER_PORT) { $env:OPLEDGER_PORT } else { "8080" }
$Url   = "http://127.0.0.1:$Port"
$Name  = "opledger"
$ProfileDir = if ($env:OPLEDGER_PROFILE_DIR) { $env:OPLEDGER_PROFILE_DIR } `
              else { Join-Path $env:LOCALAPPDATA "OPLedger\chrome-profile" }
$DevPort = if ($env:OPLEDGER_DEVTOOLS_PORT) { [int]$env:OPLEDGER_DEVTOOLS_PORT } else { [int]$Port + 1000 }

if ($Help) {
  Write-Host "OPLedger - self-hosted, private bookkeeping."
  Write-Host "Usage: opledger   (runs the container and opens a Chrome app window; close to quit)"
  exit 0
}

if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
  Write-Error "OPLedger requires Podman. Install it (e.g. 'scoop install podman') and retry."
  exit 1
}

$Chrome = @(
  (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
  (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
  (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Chrome) {
  Write-Error "OPLedger requires Google Chrome. Install it from https://www.google.com/chrome/ and retry."
  exit 1
}

$already = Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape("--user-data-dir=$ProfileDir") }
if ($already) { Write-Error "OPLedger already appears to be open. Close that window first."; exit 1 }

Write-Host "Starting OPLedger on $Url ..."
podman run -d --replace --name $Name -p "${Port}:8080" -v opledger-data:/data $Image | Out-Null

try {
  for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest -UseBasicParsing "$Url/api/setup/status" -TimeoutSec 1 | Out-Null; break }
    catch { Start-Sleep -Milliseconds 500 }
  }

  New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null
  Write-Host "OPLedger is open. Close the window to quit."
  $chromeProc = Start-Process -FilePath $Chrome -PassThru -ArgumentList @(
    "--app=$Url", "--user-data-dir=$ProfileDir", "--remote-debugging-port=$DevPort",
    "--no-first-run", "--no-default-browser-check", "--window-size=1200,860"
  )

  function Test-WindowOpen {
    try { (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$DevPort/json" -TimeoutSec 2).Content -match "127.0.0.1:$Port" }
    catch { $false }
  }

  $appeared = $false
  for ($i = 0; $i -lt 30; $i++) { if (Test-WindowOpen) { $appeared = $true; break }; Start-Sleep -Milliseconds 500 }
  if ($appeared) { while (Test-WindowOpen) { Start-Sleep -Seconds 1 } } else { $chromeProc.WaitForExit() }

  Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape("--user-data-dir=$ProfileDir") } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
finally {
  podman stop $Name 2>$null | Out-Null
  podman rm $Name 2>$null | Out-Null
}
