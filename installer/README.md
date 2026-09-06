# File Bridge - Windows installer

**Status:** UNSIGNED INTERNAL build path (no Authenticode certificate on this machine yet).  
**Primary artefact:** PowerShell one-command installer.

## One-command install (recommended)

From a PowerShell session in the extracted product tree:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-FileBridge.ps1 -RootPath "C:\Path\To\Your\Files"
```

Silent / unattended (firm IT):

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-FileBridge.ps1 -RootPath "C:\Path\To\Your\Files" -Quiet
```

Skip client config write:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-FileBridge.ps1 -RootPath "C:\Path\To\Your\Files" -SkipClientConfig
```

Skip self-test (not recommended):

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-FileBridge.ps1 -RootPath "C:\Path\To\Your\Files" -SkipSelfTest
```

## What it does

1. Checks Windows + PowerShell prerequisites (clear pass/fail).
2. Ensures `uv` is available (may download during **setup only** - not used at runtime by the bridge).
3. Creates a dedicated per-user install under `%LOCALAPPDATA%\AirgapFleet\file-bridge`.
4. Creates a pinned Python 3.11 venv and installs from this tree using `uv.lock` (lockfile-faithful).
5. Writes a launcher + uninstall registration (HKCU Add/Remove Programs).
6. Optionally writes Claude Desktop / Cursor MCP config pointing at the **local** launcher (no `uvx` / no PyPI at runtime).
7. Runs `scripts\self_test.ps1` (JSON-RPC over stdio) and **fails loudly** if it does not pass.

## Runtime air-gap

Installer may use the internet for prerequisites **during setup only**.  
Once installed, File Bridge speaks stdio JSON-RPC only - **no outbound network is required or performed for file content**.

## Environment variables

Canonical prefix: `FILE_BRIDGE_*` (e.g. `FILE_BRIDGE_ROOT_PATH`).  
Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset.

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Uninstall-FileBridge.ps1
```

Or use Settings > Apps > File Bridge (Airgap Fleet).