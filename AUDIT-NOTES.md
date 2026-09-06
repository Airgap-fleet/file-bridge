# File Bridge - Stage 2 bug audit notes (stdout / env-var)

**Date:** 2026-09-06  
**Product:** airgap-file-bridge / File Bridge (`filesystem-mcp` tree)  
**Status:** Fixes applied; UNSIGNED INTERNAL packaging follows in installer/proof-pack.

## Findings

### 1. Stdout logging (stdio MCP channel pollution)

| Area | Finding |
|------|---------|
| `src/filesystem_mcp/server.py` | `structlog.configure(...)` used the default `PrintLoggerFactory`, which writes to **stdout**. On a stdio MCP server that corrupts JSON-RPC framing. |
| Tool handlers | Use `structlog` (`log.info(...)`) - safe once factory targets stderr. |
| Root `server.py` | Alternate/legacy FastMCP stub; no explicit logging; not the packaged entry point (`filesystem_mcp.server:main`). |
| Tests / README | No regression asserting stdout stays clean. |

**Fix:** Added `configure_logging()` that:
- `logging.basicConfig(..., stream=sys.stderr, force=True)`
- `structlog.PrintLoggerFactory(file=sys.stderr)`
- Called from `main()` before `mcp.run()`

**Regression:** `tests/test_stdio_logging.py` asserts a probe log appears on stderr and **not** on stdout.

### 2. Env-var prefix mismatch

| Source | Prefix used |
|--------|-------------|
| Code (`FilesystemConfig`) before fix | `FILESYSTEM_MCP_*` |
| `.env.example`, `docker-compose.yml`, `TROUBLESHOOTING.md`, unit tests | `FILESYSTEM_MCP_*` |
| Product README, `Dockerfile`, `dxt/manifest.json`, `server.json`, `smithery.yaml` | `FILE_BRIDGE_*` |

Running installs that followed README (`FILE_BRIDGE_ROOT_PATH`) were **silently ignored** by settings; installs that followed `.env.example` worked.

**Fix (canonical + migration):**
- Canonical prefix: **`FILE_BRIDGE_*`** (matches product rename / README / DXT).
- Legacy **`FILESYSTEM_MCP_*`** still accepted when the corresponding `FILE_BRIDGE_*` is unset (`_apply_legacy_env_prefix()` on import and in `FilesystemConfig.__init__`).
- Updated `.env.example`, `docker-compose.yml`, `TROUBLESHOOTING.md`, and tests to document/use `FILE_BRIDGE_*`.
- `Dockerfile` / DXT / smithery already used `FILE_BRIDGE_*` - left aligned.

### Migration for operators

1. Prefer renaming env vars / `.env` keys from `FILESYSTEM_MCP_*` to `FILE_BRIDGE_*`.
2. No rush: legacy names continue to work until you set the new ones.
3. If both are set, **`FILE_BRIDGE_*` wins**.

## Out of scope / not changed

- Root `server.py` legacy stub (different tool surface) - packaged entry remains `airgap-file-bridge` -> `filesystem_mcp.server:main`.
- FastMCP banner / third-party library stdout (self-test sets `FASTMCP_SHOW_SERVER_BANNER=false`).
- Authenticode signing (still UNSIGNED INTERNAL).