# File Bridge - Client guide

**For:** COLP, practice manager, and firm IT evaluating or installing File Bridge  
**Product:** File Bridge (Airgap Fleet) - a local connector your AI desk uses to work with files and folders on this PC  
**Version:** 1.0.4 (see `proof-pack\VERSION.txt`)  
**Build status:** UNSIGNED INTERNAL - no Authenticode certificate on this build yet. SmartScreen or firm policy may warn; treat as an internal / pilot artefact until a signed release is issued.

This guide is plain English. Technical detail for developers lives in `README.md`.

---

## 1. What this is / who it is for

File Bridge lets your AI desk (for example Claude Desktop or Cursor) **read, write, search, and manage files inside a folder you choose on your own computer** - privately.

In client terms: ask your AI assistant to work with documents, matter packs, or shared folders on this PC, without sending those files to a File Bridge vendor cloud. The bridge is a small local program that only talks to the AI desk on the same machine. It stays inside the root folder you configure (path traversal is blocked by design).

**Who it is for**

- UK solicitors / small firms evaluating Private Desk / Airgap Fleet
- COLP / practice managers who need a clear data-boundary story for local file access
- Firm IT who need install, verify, uninstall, and support steps

**Who it is not for (yet)**

- Developers wanting package-manager workflows (see technical `README.md`)
- Anyone expecting a signed MSI for Intune today (PowerShell one-command installer is the supported Windows path; MSI is a documented next step)

---

## 2. What never leaves your PC

When File Bridge runs in its default local mode:

- Files are read and written **only under the root folder path you configure**.
- The bridge talks to your AI desk over a **local process connection** (stdio JSON-RPC; it does not open a network listening port in the air-gap demo path).
- There is **no telemetry channel**, no vendor cloud sync of file content, and no model API call made by the bridge itself.
- Logs stay on the local machine (shown in the local process output).

**Honest boundary:** your AI desk application (Claude Desktop, Cursor, and similar) is a **separate product** with its own network behaviour. This guide and the proof pack show that the **File Bridge process** does not open outbound connections while handling file operations. They do not certify third-party AI clients.

**Setup vs day-to-day use:** the installer may use the internet **during setup only** (to fetch tools and locked packages). Once installed, day-to-day file work through the bridge does not require or perform outbound network use for file content.

We do **not** claim ISO 27001, SOC 2, Cyber Essentials, Lexcel, or similar certifications in this pack. Use the proof pack as evidence for *your* auditor and firm controls.

**Sales / IT evaluation:** for a live, repeatable "nothing leaves" demo, follow `proof-pack\DEMO-CHECKLIST.md` (run twice; Resource Monitor or `proof-pack\Observe-Egress.ps1`).

---

## 3. System requirements

| Item | Requirement |
|------|-------------|
| OS | Windows 10 or Windows 11 (modest firm laptop is fine) |
| Shell | PowerShell 5.1 or later |
| Files | A local folder you want the AI desk to work inside (matter share, docs root, or similar) |
| AI desk | Claude Desktop and/or Cursor (optional if you only run the self-test) |
| Network at install | Internet may be needed **during setup** for prerequisites |
| Network at runtime | Not required for the bridge itself |
| Privileges | Per-user install under `%LOCALAPPDATA%\AirgapFleet\file-bridge` (no machine-wide admin required for the default path) |

You should receive (or extract) the product tree that includes `installer\`, `scripts\`, `proof-pack\`, `pyproject.toml`, and `uv.lock`. Do **not** clone from GitHub on the client machine as an install step.

---

## 4. Install (one command - aim under 15 minutes; must be under 30)

1. Extract the product bundle to a short path you can find again (example: `C:\AirgapFleet\file-bridge-bundle`).
2. Open **PowerShell**.
3. Change to the product folder (the folder that contains `installer\` and `pyproject.toml`):

```powershell
cd C:\Path\To\Extracted\Product
```

4. Run the installer, substituting your real files / matter folder path:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-FileBridge.ps1 -RootPath "C:\Path\To\Your\Files"
```

5. Wait for on-screen `[OK]` steps. The installer:
   - Checks Windows / PowerShell
   - Ensures setup tools are available (may download during setup only)
   - Installs into `%LOCALAPPDATA%\AirgapFleet\file-bridge`
   - Registers uninstall (Add/Remove Programs as "File Bridge (Airgap Fleet)")
   - Optionally writes local AI-desk connector settings
   - Runs a built-in self-test and **stops with a clear error** if anything fails

**Firm IT - silent / unattended:**

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-FileBridge.ps1 -RootPath "C:\Path\To\Your\Files" -Quiet
```

**Optional switches** (see `installer\README.md`): `-SkipClientConfig`, `-SkipSelfTest` (not recommended), `-Client claude_desktop|cursor|both|none`.

**Typical timing:** first install on a clean laptop often lands in the **10-20 minute** range depending on download speed for setup prerequisites; the target is **under 15 minutes** when the machine is ready, and **must stay under 30**.

---

## 5. First run / smoke check

The installer already runs a self-test unless you skipped it. To re-check at any time:

```powershell
cd C:\Path\To\Extracted\Product
powershell -ExecutionPolicy Bypass -File .\scripts\self_test.ps1 -RootPath "C:\Path\To\Your\Files"
```

**Pass looks like:** `[OK] self-test passed` (and a short status line showing pass).

Then open your AI desk and confirm the File Bridge connector appears (if client config was written). Ask it something simple - for example, list files in that root folder or search for a known document name.

If install or self-test fails, read the red `[FAIL]` line, fix that issue, and re-run the same command. Do not continue with a half-finished install.

---

## 6. Verify download

Before or after install, check the files you were given against the published checksums in `proof-pack\SHA256SUMS`:

```powershell
Get-FileHash -Algorithm SHA256 .\installer\Install-FileBridge.ps1
Get-FileHash -Algorithm SHA256 .\scripts\self_test.ps1
Get-FileHash -Algorithm SHA256 .\uv.lock
```

Compare each hash to the matching line in `proof-pack\SHA256SUMS`. To refresh sums after a rebuild, firm IT can run `proof-pack\Compute-Hashes.ps1`.

**Signing note:** this is an **UNSIGNED INTERNAL** build. The Digital Signatures tab on files will be empty, and that is expected until Authenticode signing is available (see `proof-pack\SIGNING.md`). Do not present this build as signed. Signature verification steps will be added when a signed release ships.

---

## 7. Uninstall

From the product tree:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Uninstall-FileBridge.ps1
```

Or: **Settings > Apps > File Bridge (Airgap Fleet)**.

Uninstall removes the per-user install directory and Add/Remove entry. AI-desk connector entries (if any) are left in place so you can remove them manually from Claude Desktop / Cursor settings if desired. Your documents and folders are never deleted by uninstall.

---

## 8. Support / escalate

- Escalate via your **Airgap Fleet / firm channel** (pilot contact: Brooke).
- Do not post firm file contents or screenshots of client matters on public forums.
- For evaluation evidence, attach: self-test pass output, and if used, `proof-pack\Observe-Egress.ps1` output folders plus a short screen capture per `proof-pack\DEMO-CHECKLIST.md`.

---

## Quick reference

| Task | Command / place |
|------|-----------------|
| Install | `.\installer\Install-FileBridge.ps1 -RootPath "..."` |
| Smoke check | `.\scripts\self_test.ps1 -RootPath "..."` |
| Zero-egress demo | `proof-pack\DEMO-CHECKLIST.md` |
| Checksums | `Get-FileHash` + `proof-pack\SHA256SUMS` |
| Uninstall | `.\installer\Uninstall-FileBridge.ps1` |
| Developer docs | `README.md` |
