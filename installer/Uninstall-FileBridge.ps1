<#
.SYNOPSIS
  Uninstall File Bridge per-user install.

.DESCRIPTION
  Removes the install folder, the PATH entry, the Add/Remove Programs entry and the
  "file-bridge" connector entries the installer added to Claude Desktop and Cursor.
  Each config file is backed up before it is changed. Your documents are never touched.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = $(Join-Path $env:LOCALAPPDATA "AirgapFleet\file-bridge"),
    [switch]$Quiet,
    [switch]$KeepClientConfig
)
$ErrorActionPreference = "Stop"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AirgapFleet-FileBridge"
$BinDir = Join-Path $InstallDir "bin"

function Say([string]$m) { if (-not $Quiet) { Write-Host $m } }

function Remove-BridgeEntry {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $raw = [System.IO.File]::ReadAllText($Path)
    if ([string]::IsNullOrWhiteSpace($raw)) { return }
    try { $cfg = $raw | ConvertFrom-Json -ErrorAction Stop }
    catch { Say "Left $Path unchanged (it is not valid JSON)."; return }
    if (-not ($cfg.PSObject.Properties.Name -contains "mcpServers") -or $null -eq $cfg.mcpServers) { return }
    if (-not ($cfg.mcpServers.PSObject.Properties.Name -contains "file-bridge")) { return }
    $backup = "$Path.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    Copy-Item -LiteralPath $Path -Destination $backup -Force
    $cfg.mcpServers.PSObject.Properties.Remove("file-bridge")
    $json = $cfg | ConvertTo-Json -Depth 32
    [System.IO.File]::WriteAllText($Path, $json, (New-Object System.Text.UTF8Encoding($false)))
    Say "Removed file-bridge from $Path (backup: $backup)"
}

Say "Uninstalling File Bridge from $InstallDir ..."

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -and $BinDir -and $userPath -like "*$BinDir*") {
    $parts = $userPath.Split(';') | Where-Object { $_ -and ($_ -ne $BinDir) }
    [Environment]::SetEnvironmentVariable("Path", ($parts -join ';'), "User")
    Say "Removed bin from user PATH"
}

if (-not $KeepClientConfig) {
    Remove-BridgeEntry (Join-Path $env:APPDATA "Claude\claude_desktop_config.json")
    Remove-BridgeEntry (Join-Path $env:USERPROFILE ".cursor\mcp.json")
}

if (Test-Path -LiteralPath $UninstallKey) {
    Remove-Item -LiteralPath $UninstallKey -Recurse -Force
    Say "Removed Add/Remove Programs entry"
}

if (Test-Path -LiteralPath $InstallDir) {
    Remove-Item -LiteralPath $InstallDir -Recurse -Force
    Say "Removed install directory"
}

Say "Uninstall complete. Restart Claude Desktop or Cursor so they stop looking for File Bridge."
exit 0
