# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-02

Safety and reliability release after an external code review.

### Changed (breaking)
- **Read-only by default.** `write_file` and `patch_file` are refused unless `FILE_BRIDGE_READ_ONLY=false`. The Windows installer takes `-AllowWrites`.
- **A folder is required.** The bridge no longer falls back to the current directory when `FILE_BRIDGE_ROOT_PATH` is missing, and refuses a drive root or the user's home folder unless `FILE_BRIDGE_ALLOW_BROAD_ROOT=true`.
- **`patch_file` matches exactly once by default.** New `expected_replacements` (default 1; `null` replaces every occurrence).
- `list_dir` `max_depth` now counts levels returned (1 = only that folder's contents).
- `search_files` returns paths relative to the folder (previously absolute).

### Fixed
- Folder links (NTFS junctions and symlinks) that lead outside the folder could expose file names through `list_dir` and `glob`. They are now skipped everywhere.
- Search terms starting with `-` were read by ripgrep as options and silently returned no results. Patterns are now passed with `-e`, ripgrep config files are ignored, and ripgrep can no longer read the MCP stdio channel.
- An invalid regular expression was reported as "no matches". It is now an error.
- A text file in an older Windows encoding (for example containing `£`) crashed every search. Such lines are now decoded and searched.
- Search output was decoded with the Windows code page, garbling non-English text.
- The `max_size` argument of `read_file` could raise the administrator's size limit. It can now only lower it.
- `patch_file` rewrote every line ending in the file, could not match Windows line endings, and skipped the size check before reading.
- UTF-8 text in non-Latin scripts (Greek, Cyrillic, Arabic, Chinese …) was treated as binary.
- A broken folder link made the whole listing fail.
- `list_dir` with a name filter also returned folders that did not match.
- Context lines were requested from ripgrep but never returned; column numbers were 0-based.
- `truncated` was reported when results exactly filled `max_results`.
- Error messages could include full local paths.
- Windows installer: a config file it could not parse was silently replaced with an empty one, deleting the user's other connectors. It now stops, leaves the file alone, backs up before every change and writes UTF-8 without a byte-order mark.
- Windows installer: the launcher started the server a second time after any error exit.
- Uninstaller now removes the connector entries it added to Claude Desktop and Cursor.
- `uv.lock` was git-ignored, so a fresh copy of the repository could not run the Windows installer. It is now tracked.
- Blocking file work no longer runs on the event loop.

### Added
- Previous versions of changed files are kept in `.file-bridge/versions` (`FILE_BRIDGE_BACKUP_ON_WRITE`). The AI cannot write to that folder.
- `search_files` `fixed_strings` option and `warnings` field.
- `--version`, `--help` and `--check` command-line options.
- `FILE_BRIDGE_LOG_LEVEL`.

### Removed
- Root `server.py`, an unrestricted legacy server that was not part of the package, and other unused modules.
- The out-of-date Claude extension manifest (`dxt/`), which installed a package name that does not exist.
- The unused `watchdog` dependency.

### Documentation
- Public listings (`server.json`, `smithery.yaml`) no longer mention SSE/HTTP transports or API-key authentication. Those features were never implemented.

## [1.0.0] - 2026-08-22

*Corrected 2026-10-02: the original entry listed SSE/HTTP transports, bearer-token authentication, a `--transport` flag, correlation IDs, over 90% coverage and a distroless image. None of these shipped.*

### Added
- FastMCP 3.x server over stdio
- 6 MCP tools: `read_file`, `write_file`, `list_dir`, `search_files`, `glob`, `patch_file`
- Sandbox root, symlink checks, file size limits, absolute path control
- Structured logging via structlog
- Pydantic Settings configuration with env var support
- Multi-stage Dockerfile (non-root user)
- GitHub Actions CI: lint, typecheck, test, build, PyPI publish on tags
