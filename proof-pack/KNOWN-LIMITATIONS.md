# Known limitations (honest)

1. **UNSIGNED INTERNAL** - no Authenticode signature yet; SmartScreen / firm policy may block until a signed MSI/EXE exists.
2. **MSI not built on this machine** - PowerShell one-command installer is the supported Windows path for this milestone.
3. **Env var prefix** - canonical runtime settings use **`FILE_BRIDGE_*`**. Legacy **`FILESYSTEM_MCP_*`** is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`). Prefer `FILE_BRIDGE_*` for new installs.
4. **Installer may use the internet during setup** (uv, CPython, locked wheels). Runtime bridge operation does not require network.
5. **AI desk clients are out of scope** - Claude Desktop / Cursor may open their own connections; this pack proves the bridge process path only.
6. **stdio only.** The bridge has no network transport. (Earlier listings mentioned HTTP/SSE modes; they were never implemented.)
7. **No fabricated certifications** - no ISO 27001 / SOC 2 / Cyber Essentials / Lexcel claim in this pack.
8. **Formal CycloneDX SBOM** not yet emitted; `uv.lock` is the lockfile evidence.
9. **Non-technical client README** optional for this milestone; technical `README.md` leads with the Windows installer.
10. **Files the AI reads go to the AI provider.** The zero-egress evidence covers the bridge process only. Text the AI desk reads through the bridge is sent by the AI desk to its provider.
11. **Plain-text formats only.** Word, PDF and other binary files are returned base64-encoded and are not readable by the AI through this bridge.
