# AFaaS MCP Servers — Troubleshooting Guide

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

**Applies to:** Obsidian MCP, Filesystem MCP, PostgreSQL MCP  
**Version:** 1.0.0+  
**Last Updated:** 2026-08-22

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Installation Issues](#installation-issues)
3. [Configuration Problems](#configuration-problems)
4. [Runtime Errors](#runtime-errors)
5. [Transport Issues](#transport-issues)
6. [Permission & Authentication](#permission--authentication)
7. [Platform-Specific (Windows)](#platform-specific-windows)
8. [Server-Specific Issues](#server-specific-issues)
9. [Debugging Workflow](#debugging-workflow)
10. [Getting Help](#getting-help)

---

## Quick Diagnostics

Run these first to isolate the problem:

```bash
# 1. Verify Python environment

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
python --version          # Must be 3.11+
pip list | grep -E "fastmcp|mcp|asyncpg|aiofile|watchdog|ripgrep"

# 2. Test server starts (stdio)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
cd /path/to/server
python -m server_module 2>&1 | head -20

# 3. Test JSON-RPC handshake

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python -m server_module 2>&1

# 4. Check environment variables

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
env | grep -E "OBSIDIAN_MCP|FILESYSTEM_MCP|POSTGRESQL_MCP"

# 5. Verify required paths/DSN exist

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
ls -la "$OBSIDIAN_MCP_VAULT_PATH"
ls -la "$FILE_BRIDGE_ROOT_PATH"
psql "$POSTGRESQL_MCP_DSN" -c "SELECT 1"
```

---

## Installation Issues

### `ModuleNotFoundError: No module named 'fastmcp'`

**Cause:** Dependencies not installed in current environment.

**Fix:**
```bash
# Install in development mode

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
pip install -e ".[dev]"

# Or with uv (recommended)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
uv sync --dev
```

### `ImportError: cannot import name 'FastMCP' from 'fastmcp'`

**Cause:** Version mismatch — FastMCP API changed in v3.x.

**Fix:**
```bash
pip install --upgrade "fastmcp>=3.4.7,<4.0"
# Or pin exact version in pyproject.toml

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

### `ERROR: Could not build wheels for ... asyncpg`

**Cause:** Missing PostgreSQL client libraries (Windows).

**Fix:**
```bash
# Windows: Install via conda or use pre-built wheels

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
conda install -c conda-forge asyncpg

# Or install Visual C++ Build Tools

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

### `pip install` fails with `externally-managed-environment`

**Cause:** System Python protected (PEP 668).

**Fix:**
```bash
# Use virtual environment

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# Or use pipx for CLI tools

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
pipx install obsidian-mcp
```

### DXT install fails in Claude Desktop

**Cause:** Corrupt DXT or missing manifest.

**Fix:**
```bash
# Verify DXT contents

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
python -c "
import zipfile
z = zipfile.ZipFile('server-1.0.0.dxt')
print('Contents:', [n.filename for n in z.infolist()])
for n in z.infolist():
    if n.filename == 'manifest.json':
        print(z.read(n).decode())
"

# Rebuild DXT

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
cd /path/to/server
python -m build --wheel
# DXT creation script (if available)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

---

## Configuration Problems

### `OBSIDIAN_MCP_VAULT_PATH` not set / vault not found

**Error:** `FileNotFoundError: Vault path does not exist`

**Fix:**
```bash
# Verify path exists and is readable

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
ls -la "C:/Users/YourName/YourVault"

# Set in shell

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export OBSIDIAN_MCP_VAULT_PATH="C:/Users/YourName/YourVault"

# Or in .env file (project root)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
echo "OBSIDIAN_MCP_VAULT_PATH=C:/Users/YourName/YourVault" > .env

# Windows: Use forward slashes or double backslashes

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Correct: C:/Users/Name/Vault

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Correct: C:\\Users\\Name\\Vault

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Wrong: C:\Users\Name\Vault

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

### `FILE_BRIDGE_ROOT_PATH` permission denied

**Error:** `PermissionError: [Errno 13] Permission denied`

**Fix:**
```bash
# Check permissions

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
icacls "C:\path\to\dir"  # Windows
ls -la /path/to/dir      # Linux/macOS

# Run server with appropriate user context

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Ensure the process user has read/write access to root_path

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

# For network drives: map drive letter first

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
net use Z: \\server\share
# Then use Z:\ as root_path

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

### `POSTGRESQL_MCP_DSN` connection refused

**Error:** `asyncpg.exceptions.InvalidCatalogNameError` / `Connection refused`

**Fix:**
```bash
# Test DSN directly

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
psql "postgresql://user:***@localhost:5432/db" -c "SELECT version();"

# Common DSN formats:

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Local: postgresql://user:pass@localhost:5432/dbname

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# With SSL: postgresql://user:pass@host:5432/dbname?sslmode=require

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Unix socket: postgresql://user:pass@/dbname?host=/var/run/postgresql

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

# Check PostgreSQL is running

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
systemctl status postgresql  # Linux
brew services list | grep postgresql  # macOS
# Windows: Services.msc → postgresql-x64-16

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

# Check pg_hba.conf allows connection

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# TYPE  DATABASE  USER  ADDRESS  METHOD

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# host  all       all   0.0.0.0/0  md5

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

### Environment variables not loading

**Cause:** `.env` file not in working directory or wrong prefix.

**Fix:**
```bash
# Verify .env location (must be in CWD when server starts)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
pwd
cat .env

# Or export explicitly

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export OBSIDIAN_MCP_VAULT_PATH="/absolute/path"
export FILE_BRIDGE_ROOT_PATH="/absolute/path"
export POSTGRESQL_MCP_DSN="postgresql://..."

# Check server reads them (add debug logging)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export OBSIDIAN_MCP_LOG_LEVEL=DEBUG
```

---

## Runtime Errors

### `structlog` AttributeError: `module 'structlog' has no attribute 'INFO'`

**Cause:** Using `structlog.INFO` instead of `logging.INFO`.

**Fix:** (Already patched in Filesystem MCP v1.0.0)
```python
# Wrong:

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
getattr(structlog, settings.log_level.upper())

# Correct:

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
import logging
log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
```

### `FastMCP` transport errors: `Address already in use`

**Error:** `OSError: [Errno 98] Address already in use` (port 8422/8000)

**Fix:**
```bash
# Find and kill existing process

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
lsof -ti:8422 | xargs kill -9  # Linux/macOS
netstat -ano | findstr :8422   # Windows → taskkill /PID <pid> /F

# Or change port in config

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export FILE_BRIDGE_PORT=8423
export POSTGRESQL_MCP_PORT=8424
```

### `asyncpg` pool exhausted / timeout

**Error:** `asyncpg.exceptions.TooManyConnectionsError` / `TimeoutError`

**Fix:**
```bash
# Increase pool size (max 100)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export POSTGRESQL_MCP_POOL_SIZE=20

# Check for connection leaks in client code

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Ensure clients properly close connections

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

# Monitor PostgreSQL max_connections

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
psql -c "SHOW max_connections;"
# Increase in postgresql.conf if needed

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

### `FileNotFoundError` on read/write operations

**Cause:** Path resolution issue (relative vs absolute, symlinks).

**Fix:**
```bash
# Verify working directory

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
pwd

# Check root_path config

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
echo $FILE_BRIDGE_ROOT_PATH

# Test path resolution manually

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
python -c "
from pathlib import Path
root = Path('/configured/root').resolve()
target = root / 'relative/path.md'
print('Root:', root)
print('Target:', target)
print('Exists:', target.exists())
print('Is within root:', target.is_relative_to(root))
"
```

### `ripgrep` / `rg` not found (search tools fail)

**Error:** `FileNotFoundError: [Errno 2] No such file or directory: 'rg'`

**Fix:**
```bash
# Install ripgrep

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Windows: scoop install ripgrep  OR  choco install ripgrep

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# macOS: brew install ripgrep

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Linux: apt install ripgrep / dnf install ripgrep

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

# Verify

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
rg --version
```

### `watchdog` errors on Windows (file watching)

**Error:** `OSError: [Errno 22] Invalid argument` / `Watchdog` fails to start

**Fix:**
```bash
# Windows: Use polling fallback (set in config)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export FILE_BRIDGE_WATCHDOG_POLLING=true

# Or disable file watching if not needed

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export FILE_BRIDGE_ENABLE_WATCHDOG=false

# Known issue: Watchdog on network drives fails

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Use local paths only

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

---

## Transport Issues

### stdio Transport (Default)

**Symptoms:** Client connects but no response / hanging.

**Diagnostics:**
```bash
# Test manually

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m server_module

# Check for stdout/stderr mixing

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Server MUST write JSON-RPC to stdout ONLY

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Logs go to stderr (configured via structlog)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

**Common Causes:**
- Server writes logs to stdout (breaks JSON-RPC)
- Client sends malformed JSON
- Buffering issues (use `bufsize=1` or `-u` flag)

**Fix:**
```python
# In server entry point, ensure stdout is line-buffered

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
import sys
sys.stdout.reconfigure(line_buffering=True)  # Python 3.7+

# Or run with -u

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
python -u -m server_module
```

### SSE / HTTP Transport

**Symptoms:** Connection refused / 404 / CORS errors.

**Diagnostics:**
```bash
# Test HTTP endpoint directly

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
curl -v http://localhost:8422/mcp
curl -v -X POST http://localhost:8422/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize",...}'

# Check server logs for bind address

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Must bind to 0.0.0.0 for external access, 127.0.0.1 for local only

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

**Fix:**
```bash
# Configure host/port

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export SERVER_TRANSPORT=sse
export SERVER_HOST=0.0.0.0  # External access
export SERVER_PORT=8422

# CORS: FastMCP handles automatically for SSE

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# For custom CORS, configure in FastMCP constructor

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

### Authentication failures (SSE/HTTP only)

**Error:** `401 Unauthorized` / `Invalid token`

**Fix:**
```bash
# Verify API key matches

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export SERVER_API_KEY="your-secret-key"

# Client must send Authorization header

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Authorization: Bearer your-secret-key

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

# Disable auth for local stdio (default)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export SERVER_AUTH_ENABLED=false
```

---

## Permission & Authentication

### `PermissionError: [Errno 13] Permission denied`

**Cause:** Process user lacks filesystem/database permissions.

**Fix:**
```bash
# Filesystem: Check ACLs

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
icacls "C:\path" /grant "Users:(OI)(CI)F"  # Windows full access
chmod -R u+rwX /path  # Linux/macOS

# PostgreSQL: Check user privileges

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
psql -c "GRANT ALL PRIVILEGES ON DATABASE dbname TO username;"
psql -c "GRANT ALL ON SCHEMA public TO username;"
psql -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO username;"

# Read-only mode: Ensure user has SELECT only

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

### API key rejected (remote transport)

**Fix:**
```bash
# Generate secure key

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
openssl rand -hex 32

# Set on server

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export OBSIDIAN_MCP_API_KEY="generated-key"

# Set on client (Claude Desktop config)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
{
  "mcpServers": {
    "obsidian": {
      "command": "obsidian-mcp",
      "env": {
        "OBSIDIAN_MCP_VAULT_PATH": "...",
        "OBSIDIAN_MCP_API_KEY": "generated-key"
      }
    }
  }
}

# Transport must be sse or streamable-http (not stdio)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export OBSIDIAN_MCP_TRANSPORT=sse
```

---

## Platform-Specific (Windows)

### Path Separator Issues

**Problem:** Backslashes in paths break JSON / env vars.

**Fix:**
```bash
# Always use forward slashes in config

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
OBSIDIAN_MCP_VAULT_PATH=C:/Users/Name/Vault
# NOT: C:\Users\Name\Vault

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

# In Python, use pathlib

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
from pathlib import Path
Path("C:/Users/Name/Vault")  # Works cross-platform
```

### Long Path Errors (`Filename too long` / `Error 206`)

**Fix:**
```bash
# Enable long paths in Windows 10/11

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Group Policy → Computer Configuration → Administrative Templates → System → Filesystem

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Enable "Enable Win32 long paths"

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

# Or registry:

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f

# Restart required

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

### `pywin32` version conflicts

**Error:** `hermes-agent requires pywin32<312,>=306 but you have 312`

**Fix:**
```bash
# Pin compatible version

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
pip install "pywin32>=306,<312"

# Or use uv which resolves correctly

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
uv sync
```

### Antivirus / Defender blocking server

**Symptoms:** Server starts then crashes silently / access denied.

**Fix:**
```bash
# Add exclusions for:

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# - Python executable (python.exe)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# - Project directory (C:\path\to\project\*)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# - DXT files

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

# PowerShell (Admin):

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
Add-MpPreference -ExclusionPath "C:\path\to\project"
Add-MpPreference -ExclusionProcess "python.exe"
```

### PowerShell execution policy blocks scripts

**Fix:**
```bash
# Temporary bypass

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process

# Or run from cmd.exe / Git Bash instead

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

---

## Server-Specific Issues

### Obsidian MCP

| Issue | Cause | Fix |
|-------|-------|-----|
| `Vault path does not exist` | Wrong path or env var not set | Verify `OBSIDIAN_MCP_VAULT_PATH` |
| `Frontmatter parse error` | Invalid YAML in note | Check YAML syntax; escape special chars |
| `Daily note folder not found` | Folder name mismatch | Use exact folder name from vault (case-sensitive) |
| `Search returns no results` | Ripgrep not installed / pattern wrong | Install `rg`; test pattern with `rg "pattern" vault/` |
| `Unicode decode error` | Non-UTF-8 files in vault | Set `OBSIDIAN_MCP_DEFAULT_ENCODING=latin-1` or convert files |

### Filesystem MCP

| Issue | Cause | Fix |
|-------|-------|-----|
| `Path traversal attempt blocked` | Path escapes root_path | Use relative paths; enable `allow_absolute_paths` if needed |
| `File too large` | Exceeds `max_file_size` (default 10MB) | Increase `FILE_BRIDGE_MAX_FILE_SIZE` |
| `Binary file detected` | File contains null bytes | Use `is_binary` flag in response; don't try to read as text |
| `Symlink resolution failed` | `follow_symlinks=false` (default) | Enable `FILE_BRIDGE_FOLLOW_SYMLINKS=true` |
| `Glob pattern returns nothing` | Pattern syntax error | Use `**/*.py` not `*.py` for recursive |

### PostgreSQL MCP

| Issue | Cause | Fix |
|-------|-------|-----|
| `Prepared statement already exists` | Reusing statement name in pool | Use unique query each time; asyncpg handles this |
| `Transaction aborted` | Previous error in transaction | Check `read_only` mode; ensure explicit COMMIT/ROLLBACK |
| `Parameter $1 not found` | Mismatched param count | Count `$1,$2...` in SQL matches `params` array length |
| `Read-only mode blocks write` | `POSTGRESQL_MCP_READ_ONLY=true` | Set to `false` for write operations |
| `Query timeout` | `QUERY_TIMEOUT` exceeded | Increase `POSTGRESQL_MCP_QUERY_TIMEOUT` or optimize query |
| `SSL connection required` | Server requires SSL | Add `?sslmode=require` to DSN |

---

## Debugging Workflow

### 1. Enable Debug Logging

```bash
# All servers

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export SERVER_LOG_LEVEL=DEBUG
export SERVER_LOG_JSON=false  # Human-readable

# Run and capture

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
python -m server_module 2>&1 | tee debug.log
```

### 2. Use MCP Inspector

```bash
# Start inspector (web UI at http://127.0.0.1:6274)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
npx @modelcontextprotocol/inspector

# Configure:

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Command: python

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Args: -m server_module

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Env: SERVER_LOG_LEVEL=DEBUG, SERVER_VAULT_PATH=...

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
```

### 3. Test JSON-RPC Manually

```bash
# Initialize

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python -m server_module

# List tools

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | python -m server_module

# Call tool

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read_note","arguments":{"path":"README.md"}}}' | python -m server_module
```

### 4. Check Structured Logs

```bash
# JSON logs (production)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
export SERVER_LOG_JSON=true
python -m server_module 2>&1 | jq '.'

# Filter by level

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
python -m server_module 2>&1 | jq 'select(.level=="error")'
```

### 5. Profile Performance

```bash
# Enable timing in logs (already included)

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
# Look for: "duration_ms" in log output

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

# For PostgreSQL: use explain_analyze tool

> **Env prefix:** Canonical variables are `FILE_BRIDGE_*`. Legacy `FILESYSTEM_MCP_*` is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"explain_analyze","arguments":{"sql":"SELECT * FROM large_table"}}}' | python -m server_module
```

---

## Getting Help

### Before Reporting

Collect:
1. **Server & version**: `python -m server_module --version` (or check pyproject.toml)
2. **Python version**: `python --version`
3. **OS**: `uname -a` / `systeminfo`
4. **Error output**: Full stderr + stdout
5. **Config**: Relevant env vars (sanitize secrets)
6. **Steps to reproduce**: Minimal test case

### Support Channels

| Channel | Purpose |
|---------|---------|
| **GitHub Issues** | Bug reports, feature requests |
| **GitHub Discussions** | Questions, configuration help |
| **MCP Specification** | Protocol questions: https://modelcontextprotocol.io |

### Known Limitations (v1.0.0)

- **No Windows file watching** on network drives (watchdog limitation)
- **No concurrent stdio clients** (single-process design)
- **PostgreSQL: No COPY support** (use query/execute)
- **Obsidian: No plugin API access** (file-only operations)
- **Filesystem: No recursive watch** (flat directory events only)

---

## Quick Reference: Environment Variables

### Obsidian MCP
```bash
OBSIDIAN_MCP_VAULT_PATH=              # REQUIRED
OBSIDIAN_MCP_MAX_FILE_SIZE=10485760   # 10MB
OBSIDIAN_MCP_DEFAULT_ENCODING=utf-8
OBSIDIAN_MCP_INDEX_FRONTMATTER=true
OBSIDIAN_MCP_FOLLOW_SYMLINKS=false
OBSIDIAN_MCP_TRANSPORT=stdio          # stdio|sse|streamable-http
OBSIDIAN_MCP_HOST=127.0.0.1
OBSIDIAN_MCP_PORT=8000
OBSIDIAN_MCP_PATH=/mcp
OBSIDIAN_MCP_API_KEY=                 # For SSE/HTTP only
OBSIDIAN_MCP_LOG_LEVEL=INFO
OBSIDIAN_MCP_LOG_JSON=true
```

### Filesystem MCP
```bash
FILE_BRIDGE_ROOT_PATH=             # REQUIRED
FILE_BRIDGE_MAX_FILE_SIZE=10485760
FILE_BRIDGE_FOLLOW_SYMLINKS=false
FILE_BRIDGE_ALLOW_ABSOLUTE_PATHS=false
FILE_BRIDGE_DEFAULT_ENCODING=utf-8
FILE_BRIDGE_TRANSPORT=stdio
FILE_BRIDGE_HOST=127.0.0.1
FILE_BRIDGE_PORT=8422
FILE_BRIDGE_AUTH_ENABLED=true
FILE_BRIDGE_AUTH_TOKENS=           # Comma-separated
FILE_BRIDGE_LOG_LEVEL=INFO
FILE_BRIDGE_LOG_JSON=true
```

### PostgreSQL MCP
```bash
POSTGRESQL_MCP_DSN=                   # REQUIRED
POSTGRESQL_MCP_POOL_SIZE=10
POSTGRESQL_MCP_READ_ONLY=false
POSTGRESQL_MCP_QUERY_TIMEOUT=30.0
POSTGRESQL_MCP_TRANSPORT=stdio
POSTGRESQL_MCP_HOST=127.0.0.1
POSTGRESQL_MCP_PORT=8423
POSTGRESQL_MCP_API_KEY=
POSTGRESQL_MCP_LOG_LEVEL=INFO
POSTGRESQL_MCP_LOG_JSON=true
```

---

*End of Troubleshooting Guide*