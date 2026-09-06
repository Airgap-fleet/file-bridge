# File Bridge

Bridge your AI assistant to local files - read, write, search, and manage files securely without cloud dependencies.

**Build status:** UNSIGNED INTERNAL (no Authenticode certificate on this machine yet). See `proof-pack/SIGNING.md`.

Client / COLP install guide (plain English): `CLIENT-README.md`.

## Quick start (Windows - recommended)

One-command installer (setup may use the internet once; the running bridge stays air-gapped):

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-FileBridge.ps1 -RootPath "C:\Path\To\Your\Files"
```

Post-install smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\self_test.ps1 -RootPath "C:\Path\To\Your\Files"
```

Details: `installer/README.md`. Zero-egress proof: `proof-pack/`.

Uninstall:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Uninstall-FileBridge.ps1
```

## Advanced / developer install

### uvx (no persistent install)

```bash
uvx airgap-file-bridge
```

### pip

```bash
pip install airgap-file-bridge
airgap-file-bridge
```

### MCP Client Config (Claude Desktop, Cursor, VS Code)

Prefer the Windows installer above when possible (it writes a local launcher). Manual example:

**Windows (requires full path to executable):**
`json
{
  "mcpServers": {
    "files": {
      "command": "C:\\Users\\<user>\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\airgap-file-bridge.exe",
      "env": {
        "FILESYSTEM_MCP_ROOT_PATH": "C:/path/to/files"
      }
    }
  }
}
`

**macOS/Linux (if on PATH):**
`json
{
  "mcpServers": {
    "files": {
      "command": "airgap-file-bridge",
      "env": {
        "FILESYSTEM_MCP_ROOT_PATH": "/path/to/files"
      }
    }
  }
}
`

### DXT (Claude Desktop 1-Click)

Download the .dxt from Releases and drag into Claude Desktop (when publishing a signed release).

Download the `.dxt` from Releases and drag into Claude Desktop (when publishing a signed release).

## Configuration

Canonical environment prefix: **`FILE_BRIDGE_*`**.  
Legacy **`FILESYSTEM_MCP_*`** is still accepted when the matching `FILE_BRIDGE_*` value is unset (see `AUDIT-NOTES.md`).

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `FILESYSTEM_MCP_ROOT_PATH` | Current directory | Root directory for file operations |
| `FILE_BRIDGE_MAX_FILE_SIZE` | 10MB | Max file size for operations |
| `FILE_BRIDGE_FOLLOW_SYMLINKS` | false | Follow symlinks |
| `FILE_BRIDGE_ALLOW_ABSOLUTE_PATHS` | false | Allow absolute paths outside root |
| `FILE_BRIDGE_DEFAULT_ENCODING` | utf-8 | Text encoding |

## Available Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read a file safely with size limits and binary detection |
| `write_file` | Write a file atomically with size limits |
| `list_dir` | List directory contents with optional filtering and recursion |
| `search_files` | Search file contents using ripgrep |
| `glob` | Find files matching a glob pattern |
| `patch_file` | Apply a targeted patch to a file (find and replace) |

## Transport Modes

- **stdio** (default) - For local MCP clients (Claude Desktop, etc.)
- **sse** - Server-Sent Events for HTTP clients
- **http** - Streamable HTTP for modern clients

Set via `FILE_BRIDGE_TRANSPORT` environment variable. Air-gap demos must use **stdio**.

## Windows-Specific Notes

- The executable is installed to `C:\Users\<user>\AppData\Local\hermes\hermes-agent\venv\Scripts\airgap-file-bridge.exe` when using Hermes
- **Always use the full `.exe` path in MCP client configs on Windows** — bare commands like `airgap-file-bridge` will fail with `ENOENT` because the venv Scripts folder is not on system PATH
- Use forward slashes in environment variable values (`C:/path/to/files`) — they work fine in JSON
- Escape backslashes in JSON command paths (`C:\Users\...`)

## Why File Bridge?

- **Local-first** - Your files never leave your machine
- **Air-gapped ready** - No cloud dependencies, works offline
- **Security hardened** - Path traversal protection, size limits, symlink control, binary detection
- **Multiple transports** - stdio, SSE, Streamable HTTP
- **Ripgrep powered** - Fast regex search with context

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
uv run pytest -v

# Check code quality
uv run ruff check .
uv run mypy .
```

## License

MIT
