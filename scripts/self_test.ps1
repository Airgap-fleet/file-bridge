<#
.SYNOPSIS
  Post-install / developer JSON-RPC smoke test for file-bridge.
  Fails loudly (non-zero exit) if stdout is polluted or tools do not respond.
#>
[CmdletBinding()]
param(
    [string]$FileBridgeExe = "",
    [string]$PythonExe = "",
    [Parameter(Mandatory = $true)]
    [string]$RootPath,
    [int]$TimeoutSec = 25
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$SelfTestPy = Join-Path $PSScriptRoot "self_test.py"

if (-not (Test-Path -LiteralPath $SelfTestPy)) {
    Write-Host "[FAIL] Missing $SelfTestPy" -ForegroundColor Red
    exit 2
}
if (-not (Test-Path -LiteralPath $RootPath -PathType Container)) {
    Write-Host "[FAIL] RootPath not a directory: $RootPath" -ForegroundColor Red
    exit 2
}

if (-not $PythonExe) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "AirgapFleet\file-bridge\venv\Scripts\python.exe"),
        (Join-Path $RepoRoot ".venv\Scripts\python.exe")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $PythonExe = $c; break }
    }
}
if (-not $PythonExe) {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { $PythonExe = $py.Source }
}
if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Host "[FAIL] No Python interpreter found for self-test." -ForegroundColor Red
    exit 2
}

if (-not $FileBridgeExe) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "AirgapFleet\file-bridge\venv\Scripts\airgap-file-bridge.exe"),
        (Join-Path $RepoRoot ".venv\Scripts\airgap-file-bridge.exe")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $FileBridgeExe = $c; break }
    }
}

Write-Host "=== file-bridge self-test ==="
Write-Host "Python:  $PythonExe"
Write-Host "Exe:     $(if ($FileBridgeExe) { $FileBridgeExe } else { '(module fallback)' })"
Write-Host "Root:    $RootPath"
Write-Host ""

$argList = @(
    $SelfTestPy,
    "--python", $PythonExe,
    "--root", $RootPath,
    "--timeout", "$TimeoutSec"
)
if ($FileBridgeExe -and (Test-Path $FileBridgeExe)) {
    $argList += @("--exe", $FileBridgeExe)
}

& $PythonExe @argList
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Host ""
    Write-Host "[FAIL] self-test exited $code" -ForegroundColor Red
    exit $code
}
Write-Host ""
Write-Host "[OK] self-test passed" -ForegroundColor Green
exit 0