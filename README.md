# File Bridge

A small local MCP server that lets an AI assistant (Claude Desktop, Cursor, VS Code) read and search the files in **one folder you choose**. It is read-only unless you switch writing on, and it makes no network connections of its own.

**What it does not do:** when your AI assistant reads a file through the bridge, the assistant sends that text to its own provider (Anthropic, OpenAI, …) under that provider's terms. File Bridge controls *which* files the assistant can reach; it does not hide their contents from the assistant.

**Build status:** UNSIGNED INTERNAL (no Authenticode certificate yet). See `proof-pack/SIGNING.md`.

Client / COLP install guide (plain English): `CLIENT-README.md`.

## Quick start (Windows - recommended)

One-command installer (setup may use the internet once; the running bridge makes no network connections):

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-FileBridge.ps1 -RootPath "C:\Path\To\Your\Files"
```

Add `-AllowWrites` if the AI should be able to create and edit files. Without it the bridge is read-only.

Post-install smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\self_test.ps1 -RootPath "C:\Path\To\Your\Files"
```

Details: `installer/README.md`. Zero-egress proof: `proof-pack/`.

Uninstall (also removes the connector entries it added to Claude Desktop and Cursor):

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Uninstall-FileBridge.ps1
```

## Advanced / developer install

```bash
pip install airgap-file-bridge
FILE_BRIDGE_ROOT_PATH=/path/to/files airgap-file-bridge --check
```

`--check` confirms the configuration and exits. `--version` prints the version.

### MCP client config (Claude Desktop, Cursor, VS Code)

Prefer the Windows installer when possible (it writes a local launcher for you). Manual example for Windows, using the full path to the executable:

```json
{
  "mcpServers": {
    "file-bridge": {
      "command": "C:\\Path\\To\\venv\\Scripts\\airgap-file-bridge.exe",
      "env": {
        "FILE_BRIDGE_ROOT_PATH": "C:/Path/To/Files",
        "FILE_BRIDGE_READ_ONLY": "true"
      }
    }
  }
}
```

macOS / Linux, if the command is on PATH:

```json
{
  "mcpServers": {
    "file-bridge": {
      "command": "airgap-file-bridge",
      "env": { "FILE_BRIDGE_ROOT_PATH": "/path/to/files" }
    }
  }
}
```

## Configuration

Environment prefix: **`FILE_BRIDGE_*`**. Legacy `FILESYSTEM_MCP_*` names still work when the matching `FILE_BRIDGE_*` value is unset.

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `FILE_BRIDGE_ROOT_PATH` | *(required)* | The one folder the AI may use. The bridge will not start without it, and refuses a whole drive or your entire user folder. |
| `FILE_BRIDGE_READ_ONLY` | `true` | Set to `false` to allow `write_file` and `patch_file`. |
| `FILE_BRIDGE_BACKUP_ON_WRITE` | `true` | Keep the previous version of a changed file in `.file-bridge/versions`. |
| `FILE_BRIDGE_MAX_FILE_SIZE` | 10 MB | Max file size for operations. A tool call can lower it, never raise it. |
| `FILE_BRIDGE_FOLLOW_SYMLINKS` | `false` | Allow paths through symlinks. Links can never lead outside the folder either way. |
| `FILE_BRIDGE_ALLOW_ABSOLUTE_PATHS` | `false` | Accept absolute paths (they must still be inside the folder). |
| `FILE_BRIDGE_DEFAULT_ENCODING` | `utf-8` | Text encoding. Files saved in older Windows encodings are read automatically. |
| `FILE_BRIDGE_ALLOW_BROAD_ROOT` | `false` | Allow a drive root or home folder as the root (not advised). |
| `FILE_BRIDGE_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. Logs go to stderr. |

## Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read a text file (any language, including older Windows encodings). Binary files come back base64-encoded. |
| `list_dir` | List a folder, optionally recursively, with a name filter and a depth limit. |
| `search_files` | Search file contents with ripgrep: regex or plain text, context lines, file filters. |
| `glob` | Find files by pattern, e.g. `**/*.md`. Patterns cannot contain `..`. |
| `write_file` | Write a file atomically. Read-only mode refuses it. |
| `patch_file` | Replace exact text. Must match exactly once unless you say otherwise. Keeps encoding and line endings. Read-only mode refuses it. |

## Safety behaviour

- Every path is resolved and must stay inside the folder. Folder links (symlinks and NTFS junctions) that lead elsewhere are not listed, searched or read.
- Search terms are always passed to ripgrep as patterns, never as options, and ripgrep cannot read the MCP channel.
- Writes are atomic, and the previous version is kept in `.file-bridge/versions`, which the AI cannot change.
- The bridge talks over stdio only. It opens no ports and makes no network calls.

## Development

```bash
pip install -e ".[dev]"
pytest -v
ruff check src/ tests/
mypy --config-file mypy.ini --strict src/filesystem_mcp
```

Search tests need ripgrep (`rg`) on PATH.

## License

MIT
