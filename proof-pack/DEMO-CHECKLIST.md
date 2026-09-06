# Zero-egress live demo checklist (run twice)

**Goal:** On a visible network monitor, run a realistic file query through File Bridge and show **zero outbound connections from the bridge process**. Recordable as a short screen capture; must be live-repeatable.

**Signing note:** This demo uses the UNSIGNED INTERNAL build until Authenticode is available.

## Before you start

1. Install via `installer\Install-FileBridge.ps1` (or use the repo `.venv` for an internal dry-run).
2. Have a small folder ready (any directory with a couple of text files is fine for dry-runs).
3. Close unrelated heavy network apps if you want a cleaner Resource Monitor view (optional).

## Pass 1

### A. Open a network monitor (visible on screen)

**Option A (no extra tools):** Windows Resource Monitor

```powershell
resmon.exe
```

- Open the **Network** tab.
- Leave it visible for the recording.

**Option B (scripted snapshot):**

```powershell
powershell -ExecutionPolicy Bypass -File .\proof-pack\Observe-Egress.ps1 -RootPath "C:\Path\To\Files" -OutDir "$env:TEMP\file-bridge-egress-pass1"
```

### B. Run a realistic query through the bridge

Use the JSON-RPC self-test (exercises `initialize`, `tools/list`, and `list_dir` against the root path):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\self_test.ps1 -RootPath "C:\Path\To\Files"
```

Expected: `[OK] self-test passed` and a JSON `status=pass` line.

### C. Show zero outbound

- In Resource Monitor > Network: confirm the `airgap-file-bridge` / `python` bridge process shows **no remote TCP connections** during the query.
- If using `Observe-Egress.ps1`: open `connections-during.json` / summary - remote endpoints for the bridge PID should be empty (or only loopback, which is not egress).

### D. Tick

- [ ] Monitor visible
- [ ] Query completed successfully
- [ ] No outbound from bridge process
- [ ] Pass 1 timestamp: __________

## Pass 2 (must be consistent)

Repeat A-C immediately (or after a reboot - both are valid). Do not "warm up" with hidden network steps.

- [ ] Monitor visible
- [ ] Query completed successfully
- [ ] No outbound from bridge process
- [ ] Pass 2 timestamp: __________

## Result

If both passes succeed with matching "no outbound" evidence, the proof pack demo is **live-repeatable**. Attach screen capture + the `Observe-Egress` output folders to the pilot record.

## What this does *not* prove

- Behaviour of Claude Desktop / Cursor / other AI clients (separate products).
- Behaviour of optional HTTP/SSE transport modes (not the default; do not use for air-gap demos).
- Future update mechanisms (must remain customer-controlled; see KNOWN-LIMITATIONS.md).