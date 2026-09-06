<#
.SYNOPSIS
  One-command Windows installer for File Bridge (UNSIGNED INTERNAL).

.DESCRIPTION
  Installs airgap-file-bridge into a dedicated per-user directory with a pinned
  Python 3.11 venv from uv.lock, registers uninstall, optionally configures
  MCP clients, and runs a JSON-RPC self-test that fails loudly on error.

  Setup may use the internet for prerequisites (uv / Python / locked deps).
  The running bridge is stdio-only and must remain air-gapped for file content.

.PARAMETER RootPath
  Sandbox / root directory for file operations. Required unless -SkipClientConfig.

.PARAMETER InstallDir
  Override install root. Default: %LOCALAPPDATA%\AirgapFleet\file-bridge

.PARAMETER Quiet
  Silent / unattended mode (still fails loudly on error).

.PARAMETER SkipClientConfig
  Do not write Claude Desktop / Cursor MCP config.

.PARAMETER SkipSelfTest
  Skip post-install JSON-RPC self-test (not recommended).

.PARAMETER Client
  claude_desktop | cursor | both | none

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\installer\Install-FileBridge.ps1 -RootPath "D:\Matters\SharedDocs"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$RootPath,

    [Parameter(Mandatory = $false)]
    [string]$InstallDir = $(Join-Path $env:LOCALAPPDATA "AirgapFleet\file-bridge"),

    [switch]$Quiet,
    [switch]$SkipClientConfig,
    [switch]$SkipSelfTest,

    [ValidateSet("claude_desktop", "cursor", "both", "none")]
    [string]$Client = "both"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProductName = "File Bridge"
$Publisher = "Airgap Fleet"
$ProductVersion = "1.0.4"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AirgapFleet-FileBridge"
$SigningStatus = "UNSIGNED INTERNAL - no Authenticode certificate present on build machine"

function Write-Step {
    param([string]$Message, [ValidateSet("INFO","PASS","FAIL","WARN")][string]$Level = "INFO")
    if ($Quiet -and $Level -eq "INFO") { return }
    $prefix = switch ($Level) {
        "INFO" { "[ ]" }
        "PASS" { "[OK]" }
        "FAIL" { "[FAIL]" }
        "WARN" { "[WARN]" }
    }
    $line = "$prefix $Message"
    if ($Level -eq "FAIL") { Write-Host $line -ForegroundColor Red }
    elseif ($Level -eq "PASS") { Write-Host $line -ForegroundColor Green }
    elseif ($Level -eq "WARN") { Write-Host $line -ForegroundColor Yellow }
    else { Write-Host $line }
}

function Fail-Loud {
    param([string]$Message, [int]$Code = 1)
    Write-Step $Message -Level FAIL
    Write-Host ""
    Write-Host "Installation stopped. Fix the issue above and re-run this script." -ForegroundColor Red
    Write-Host "Signing status: $SigningStatus" -ForegroundColor Yellow
    exit $Code
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
    Fail-Loud "Cannot find pyproject.toml above installer\. Run this script from the product tree."
}
if (-not (Test-Path (Join-Path $RepoRoot "uv.lock"))) {
    Fail-Loud "uv.lock missing - cannot perform a lockfile-faithful install."
}

Write-Host ""
Write-Host "=== $ProductName installer ($ProductVersion) ===" -ForegroundColor Cyan
Write-Host "Signing: $SigningStatus" -ForegroundColor Yellow
Write-Host "Install dir: $InstallDir"
Write-Host "Source tree: $RepoRoot"
Write-Host ""

Write-Step "Checking Windows / PowerShell..."
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Fail-Loud "PowerShell 5.1+ required. Found: $($PSVersionTable.PSVersion)"
}
Write-Step "PowerShell $($PSVersionTable.PSVersion) OK" -Level PASS

if (-not $SkipClientConfig) {
    if ([string]::IsNullOrWhiteSpace($RootPath)) {
        Fail-Loud "-RootPath is required unless you pass -SkipClientConfig."
    }
    if (-not (Test-Path -LiteralPath $RootPath -PathType Container)) {
        Fail-Loud "Root path does not exist or is not a directory: $RootPath"
    }
    $RootPath = (Resolve-Path -LiteralPath $RootPath).Path
    Write-Step "Root path OK: $RootPath" -Level PASS
}

Write-Step "Checking for uv (package manager)..."
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Step "uv not found - attempting install (setup-time network use)..." -Level WARN
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        $localBin = Join-Path $env:USERPROFILE ".local\bin"
        $hermesBin = Join-Path $env:USERPROFILE "AppData\Local\hermes\bin"
        $env:Path = "$localBin;$hermesBin;$env:Path"
        $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
        if (-not $uvCmd) { Fail-Loud "uv install appeared to run but uv is still not on PATH. Add uv to PATH and retry." }
    } catch {
        Fail-Loud "Failed to install uv: $($_.Exception.Message). Install from https://docs.astral.sh/uv/ and retry."
    }
}
Write-Step "uv available: $((Get-Command uv).Source)" -Level PASS

Write-Step "Preparing install directory..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$VenvDir = Join-Path $InstallDir "venv"
$BinDir = Join-Path $InstallDir "bin"
$LogsDir = Join-Path $InstallDir "logs"
$SrcMirror = Join-Path $InstallDir "src-tree"
New-Item -ItemType Directory -Force -Path $BinDir, $LogsDir | Out-Null

Write-Step "Copying product sources into install dir..."
$mirrorItems = @("pyproject.toml", "uv.lock", "README.md", "src", "scripts", "proof-pack", "installer")
if (Test-Path -LiteralPath $SrcMirror) {
    Remove-Item -LiteralPath $SrcMirror -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $SrcMirror | Out-Null
foreach ($item in $mirrorItems) {
    $src = Join-Path $RepoRoot $item
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $SrcMirror $item) -Recurse -Force
    }
}
Write-Step "Source mirror ready" -Level PASS

Write-Step "Creating Python 3.11 venv (may download CPython once during setup)..."
try {
    & uv python install 3.11
    if ($LASTEXITCODE -ne 0) { throw "uv python install 3.11 exited $LASTEXITCODE" }
    if (Test-Path $VenvDir) { Remove-Item -LiteralPath $VenvDir -Recurse -Force }
    & uv venv --python 3.11 $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "uv venv exited $LASTEXITCODE" }
} catch {
    Fail-Loud "Failed to create Python 3.11 venv: $($_.Exception.Message)"
}
Write-Step "Venv created at $VenvDir" -Level PASS

Write-Step "Installing file-bridge from lockfile (setup-time network OK)..."
$pythonExe = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $pythonExe)) { Fail-Loud "python.exe missing in venv: $pythonExe" }

Push-Location $SrcMirror
try {
    & uv sync --frozen --python $pythonExe
    if ($LASTEXITCODE -ne 0) {
        Write-Step "uv sync --frozen failed; trying uv pip install -e ." -Level WARN
        & uv pip install --python $pythonExe -e .
        if ($LASTEXITCODE -ne 0) { throw "uv pip install -e . failed with exit $LASTEXITCODE" }
    }
} catch {
    Pop-Location
    Fail-Loud "Dependency install failed: $($_.Exception.Message)"
}
Pop-Location

$fbExe = Join-Path $VenvDir "Scripts\airgap-file-bridge.exe"
if (-not (Test-Path $fbExe)) {
    Write-Step "airgap-file-bridge.exe not found after install - checking module import..." -Level WARN
    & $pythonExe -c "import filesystem_mcp.server; print('import-ok')"
    if ($LASTEXITCODE -ne 0) { Fail-Loud "file-bridge did not install correctly (no exe, import failed)." }
}
Write-Step "Package install OK" -Level PASS

$launcherPs1 = Join-Path $BinDir "file-bridge.ps1"
$launcherCmd = Join-Path $BinDir "file-bridge.cmd"
@"
@echo off
REM File Bridge launcher - local stdio only; no network.
set "VIRTUAL_ENV=$VenvDir"
if defined FILE_BRIDGE_ROOT_PATH goto run
if defined FILESYSTEM_MCP_ROOT_PATH set "FILE_BRIDGE_ROOT_PATH=%FILESYSTEM_MCP_ROOT_PATH%"
:run
"$fbExe" %*
if errorlevel 1 (
  "$pythonExe" -m filesystem_mcp.server %*
)
"@ | Set-Content -Path $launcherCmd -Encoding ascii

@"
# File Bridge launcher (PowerShell) - local stdio only; no network.
`$env:VIRTUAL_ENV = '$VenvDir'
if (-not `$env:FILE_BRIDGE_ROOT_PATH -and `$env:FILESYSTEM_MCP_ROOT_PATH) {
    `$env:FILE_BRIDGE_ROOT_PATH = `$env:FILESYSTEM_MCP_ROOT_PATH
}
`$exe = '$fbExe'
if (Test-Path `$exe) { & `$exe @args; exit `$LASTEXITCODE }
& '$pythonExe' -m filesystem_mcp.server @args
exit `$LASTEXITCODE
"@ | Set-Content -Path $launcherPs1 -Encoding utf8

Write-Step "Adding bin dir to user PATH (if missing)..."
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
if ($userPath -notlike "*$BinDir*") {
    $newPath = if ($userPath.Trim().Length -gt 0) { $userPath.TrimEnd(';') + ";" + $BinDir } else { $BinDir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:Path = "$BinDir;$env:Path"
    Write-Step "PATH updated (new shells will see file-bridge)" -Level PASS
} else {
    Write-Step "PATH already contains bin dir" -Level PASS
}

if (-not $SkipClientConfig -and $Client -ne "none") {
    Write-Step "Writing MCP client config (local launcher; no uvx at runtime)..."
    $envMap = @{ FILE_BRIDGE_ROOT_PATH = $RootPath; FILE_BRIDGE_TRANSPORT = "stdio" }
    $command = $launcherCmd
    if ($Client -eq "claude_desktop" -or $Client -eq "both") {
        $cd = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
        $existing = [pscustomobject]@{ mcpServers = [pscustomobject]@{} }
        if (Test-Path $cd) {
            try { $existing = Get-Content $cd -Raw | ConvertFrom-Json } catch { }
        }
        if (-not $existing.mcpServers) {
            $existing | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
        }
        $serverObj = [pscustomobject]@{
            command = $command
            args    = @()
            env     = [pscustomobject]$envMap
        }
        $existing.mcpServers | Add-Member -NotePropertyName "file-bridge" -NotePropertyValue $serverObj -Force
        $cdDir = Split-Path $cd -Parent
        if (-not (Test-Path $cdDir)) { New-Item -ItemType Directory -Force -Path $cdDir | Out-Null }
        ($existing | ConvertTo-Json -Depth 8) | Set-Content -Path $cd -Encoding utf8
        Write-Step "Claude Desktop config updated: $cd" -Level PASS
    }
    if ($Client -eq "cursor" -or $Client -eq "both") {
        $cu = Join-Path $env:USERPROFILE ".cursor\mcp.json"
        $existing = [pscustomobject]@{ mcpServers = [pscustomobject]@{} }
        if (Test-Path $cu) {
            try { $existing = Get-Content $cu -Raw | ConvertFrom-Json } catch { }
        }
        if (-not $existing.mcpServers) {
            $existing | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
        }
        $serverObj = [pscustomobject]@{
            command = $command
            args    = @()
            env     = [pscustomobject]$envMap
        }
        $existing.mcpServers | Add-Member -NotePropertyName "file-bridge" -NotePropertyValue $serverObj -Force
        $cuDir = Split-Path $cu -Parent
        if (-not (Test-Path $cuDir)) { New-Item -ItemType Directory -Force -Path $cuDir | Out-Null }
        ($existing | ConvertTo-Json -Depth 8) | Set-Content -Path $cu -Encoding utf8
        Write-Step "Cursor config updated: $cu" -Level PASS
    }
} else {
    Write-Step "Skipped MCP client config" -Level WARN
}

Write-Step "Registering uninstall..."
$uninstallPs1 = Join-Path $InstallDir "Uninstall-FileBridge.ps1"
Copy-Item -LiteralPath (Join-Path $RepoRoot "installer\Uninstall-FileBridge.ps1") -Destination $uninstallPs1 -Force -ErrorAction SilentlyContinue
if (-not (Test-Path $uninstallPs1)) {
    @"
Remove-Item -LiteralPath '$InstallDir' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath '$UninstallKey' -Recurse -Force -ErrorAction SilentlyContinue
"@ | Set-Content $uninstallPs1 -Encoding utf8
}

New-Item -Path $UninstallKey -Force | Out-Null
Set-ItemProperty -Path $UninstallKey -Name "DisplayName" -Value "$ProductName (Airgap Fleet)"
Set-ItemProperty -Path $UninstallKey -Name "DisplayVersion" -Value $ProductVersion
Set-ItemProperty -Path $UninstallKey -Name "Publisher" -Value $Publisher
Set-ItemProperty -Path $UninstallKey -Name "InstallLocation" -Value $InstallDir
Set-ItemProperty -Path $UninstallKey -Name "DisplayIcon" -Value $pythonExe
Set-ItemProperty -Path $UninstallKey -Name "UninstallString" -Value "powershell.exe -ExecutionPolicy Bypass -File `"$uninstallPs1`""
Set-ItemProperty -Path $UninstallKey -Name "NoModify" -Value 1 -Type DWord
Set-ItemProperty -Path $UninstallKey -Name "NoRepair" -Value 1 -Type DWord
Set-ItemProperty -Path $UninstallKey -Name "Comments" -Value $SigningStatus
Write-Step "Add/Remove Programs entry written (HKCU)" -Level PASS

$gitCommit = "unknown"
try {
    Push-Location $RepoRoot
    $gitCommit = (git rev-parse HEAD 2>$null)
    if (-not $gitCommit) { $gitCommit = "unknown" }
    Pop-Location
} catch { }
@"
product=$ProductName
version=$ProductVersion
git_commit=$gitCommit
install_dir=$InstallDir
signing=$SigningStatus
installed_utc=$((Get-Date).ToUniversalTime().ToString('o'))
"@ | Set-Content (Join-Path $InstallDir "VERSION.txt") -Encoding utf8

if (-not $SkipSelfTest) {
    Write-Step "Running JSON-RPC self-test (must pass)..."
    $selfTest = Join-Path $RepoRoot "scripts\self_test.ps1"
    if (-not (Test-Path $selfTest)) { Fail-Loud "self_test.ps1 missing at $selfTest" }
    $testRoot = if ($RootPath) { $RootPath } else { Join-Path $env:TEMP ("file-bridge-selftest-" + [guid]::NewGuid().ToString("N")) }
    $createdTemp = $false
    if (-not (Test-Path $testRoot)) {
        New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
        Set-Content -Path (Join-Path $testRoot "smoke.txt") -Value "file-bridge self-test marker" -Encoding utf8
        $createdTemp = $true
    }
    & powershell -ExecutionPolicy Bypass -File $selfTest -FileBridgeExe $fbExe -PythonExe $pythonExe -RootPath $testRoot
    $st = $LASTEXITCODE
    if ($createdTemp) { Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue }
    if ($st -ne 0) {
        Fail-Loud "Self-test FAILED (exit $st). Install is incomplete - see self-test output above."
    }
    Write-Step "Self-test PASSED" -Level PASS
} else {
    Write-Step "Skipped self-test (-SkipSelfTest)" -Level WARN
}

Write-Host ""
Write-Host "=== Install complete ===" -ForegroundColor Green
Write-Host "Launcher: $launcherCmd"
Write-Host "Install:  $InstallDir"
Write-Host "Signing:  $SigningStatus"
Write-Host "Proof:    see proof-pack\ in the product tree / install mirror"
Write-Host ""
Write-Host "Next: restart your AI client, then run the zero-egress demo in proof-pack\DEMO-CHECKLIST.md"
exit 0