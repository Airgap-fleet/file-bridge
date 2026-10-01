"""Core business logic for Filesystem MCP Server.

This module contains all filesystem operations without any FastMCP dependencies,
making it fully testable in isolation.
"""

import base64
import codecs
import fnmatch
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from filesystem_mcp.models import (
    BRIDGE_DATA_DIR,
    DirEntry,
    FilesystemConfig,
    GlobRequest,
    GlobResponse,
    ListDirRequest,
    ListDirResponse,
    PatchFileRequest,
    PatchFileResponse,
    ReadFileRequest,
    ReadFileResponse,
    SearchFilesRequest,
    SearchFilesResponse,
    SearchMatch,
    WriteFileRequest,
    WriteFileResponse,
)

log = structlog.get_logger()

_IS_WINDOWS = os.name == "nt"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
# Walking stops after this many entries so a huge tree cannot stall the bridge.
_MAX_WALK_ENTRIES = 200_000
_SEARCH_TIMEOUT_SECONDS = 30


class FilesystemError(Exception):
    """Base exception for filesystem operations."""

    def __init__(
        self, message: str, code: str = "FILESYSTEM_ERROR", details: dict[str, Any] | None = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class SecurityError(FilesystemError):
    """Security-related filesystem error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="SECURITY_ERROR", details=details)


class FileSizeError(FilesystemError):
    """File size limit exceeded."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="FILE_SIZE_ERROR", details=details)


class ConfigError(FilesystemError):
    """The bridge is not configured safely enough to start."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="CONFIG_ERROR", details=details)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _is_within(path: str | Path, root: Path) -> bool:
    """True when an absolute path is root itself or inside it."""
    p = _norm(str(path))
    r = _norm(str(root))
    return p == r or p.startswith(r.rstrip("\\/") + os.sep)


def _safe_is_dir(entry: os.DirEntry[str]) -> bool:
    try:
        return entry.is_dir()
    except OSError:
        return False


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a glob with ** support into a regex for '/'-joined relative paths."""
    out: list[str] = []
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if pattern.startswith("**/", i):
                out.append("(?:[^/]*/)*")
                i += 3
                continue
            if pattern.startswith("**", i):
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = pattern.find("]", i + 2)
            if j == -1:
                out.append(re.escape(c))
            else:
                body = pattern[i + 1 : j].replace("\\", "\\\\")
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append(f"[{body}]")
                i = j + 1
                continue
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("".join(out) + r"\Z", re.IGNORECASE if _IS_WINDOWS else 0)


def _rg_text(field: Any) -> str:
    """Read a ripgrep JSON text field, which is {"text": ...} or base64 {"bytes": ...}."""
    if not isinstance(field, dict):
        return ""
    if isinstance(field.get("text"), str):
        return str(field["text"])
    raw = field.get("bytes")
    if not isinstance(raw, str):
        return ""
    data = base64.b64decode(raw)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        # Legacy Windows text files (e.g. a '£' saved as cp1252)
        return data.decode("cp1252", errors="replace")


class FilesystemCore:
    """Core filesystem operations - no FastMCP dependencies."""

    def __init__(self, config: FilesystemConfig | None = None):
        self.config = config or FilesystemConfig()
        root = self.config.root_path
        if root is None:
            raise ConfigError(
                "No folder is configured. Set FILE_BRIDGE_ROOT_PATH to the one folder "
                "the AI may use."
            )
        if not root.is_dir():
            raise ConfigError(
                "The configured folder does not exist or is not a folder.",
                details={"root_path": str(root)},
            )
        if not self.config.allow_broad_root:
            is_drive_root = root == Path(root.anchor) and not root.drive.startswith("\\\\")
            is_home = _norm(str(root)) == _norm(str(Path.home().resolve()))
            if is_drive_root or is_home:
                raise ConfigError(
                    "The configured folder is a whole drive or your entire user folder. "
                    "Choose a specific folder, or set FILE_BRIDGE_ALLOW_BROAD_ROOT=true.",
                    details={"root_path": str(root)},
                )
        self.root: Path = root
        log.info(
            "filesystem_core_initialized", root_path=str(root), read_only=self.config.read_only
        )

    # ------------------------------------------------------------------ paths

    def _resolve_path(self, path: str) -> Path:
        """Resolve a user-provided path to an absolute path within the root."""
        try:
            if Path(path).is_absolute():
                if not self.config.allow_absolute_paths:
                    raise SecurityError(
                        "Absolute paths are not allowed (allow_absolute_paths=False)",
                        details={"path": path},
                    )
                resolved = Path(path).resolve()
            else:
                resolved = (self.root / path).resolve()
        except (OSError, ValueError) as e:
            raise FilesystemError(f"Invalid path: {path!r}", code="INVALID_PATH") from e

        if not _is_within(resolved, self.root):
            raise SecurityError(
                f"Path '{path}' resolves outside the configured root directory",
                details={"requested_path": path},
            )

        # Symlink protection: check each component of the requested path
        if not self.config.follow_symlinks:
            check_path = self.root
            for part in Path(path).parts:
                check_path = check_path / part
                if check_path.is_symlink():
                    raise SecurityError(
                        "Symlinks are not allowed (follow_symlinks=False)",
                        details={"path": path},
                    )

        return resolved

    def _relative(self, path: Path) -> str:
        return str(path.relative_to(self.root))

    def _classify(self, entry: os.DirEntry[str]) -> tuple[bool, bool]:
        """Return (is_link, leaves_root) for a directory entry.

        Symlinks and NTFS junctions are links. OneDrive placeholders are reparse
        points too, but they resolve to themselves, so they count as normal files.
        """
        try:
            attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        except OSError:
            attrs = 0
        if not (entry.is_symlink() or attrs & _FILE_ATTRIBUTE_REPARSE_POINT):
            return False, False
        try:
            real = os.path.realpath(entry.path)
        except (OSError, ValueError):
            return True, True
        if _norm(real) == _norm(entry.path):
            return False, False
        return True, not _is_within(real, self.root)

    def _scandir(self, current: Path) -> list[os.DirEntry[str]]:
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except PermissionError:
            log.warning("permission_denied_listing", path=self._relative(current))
            return []
        except OSError as e:
            log.warning("listing_failed", path=self._relative(current), error=str(e))
            return []
        entries.sort(key=lambda e: (not _safe_is_dir(e), e.name.lower()))
        return entries

    def _walk(self, start: Path, *, include_hidden: bool) -> Iterator[tuple[Path, bool]]:
        """Yield (path, is_dir) for everything under start, never leaving the root."""
        stack = [start]
        seen = 0
        while stack:
            current = stack.pop()
            subdirs: list[Path] = []
            for entry in self._scandir(current):
                seen += 1
                if seen > _MAX_WALK_ENTRIES:
                    log.warning("walk_limit_reached", limit=_MAX_WALK_ENTRIES)
                    return
                if entry.name == BRIDGE_DATA_DIR:
                    continue
                if not include_hidden and entry.name.startswith("."):
                    continue
                is_link, leaves_root = self._classify(entry)
                if leaves_root:
                    continue
                is_dir = _safe_is_dir(entry)
                yield Path(entry.path), is_dir
                if is_dir and not is_link:
                    subdirs.append(Path(entry.path))
            stack.extend(reversed(subdirs))

    # -------------------------------------------------------------- helpers

    def _size_limit(self, requested: int | None) -> int:
        cap = self.config.max_file_size
        return min(requested, cap) if requested else cap

    def _check_file_size(self, path: Path, limit: int | None = None) -> None:
        """Check if file size is within limits."""
        limit = self._size_limit(limit)
        if path.exists() and path.is_file():
            size = path.stat().st_size
            if size > limit:
                raise FileSizeError(
                    f"File size {size} bytes exceeds limit of {limit} bytes",
                    details={"file_size": size, "limit": limit},
                )

    def _is_binary(self, content: bytes) -> bool:
        """Heuristic to detect binary files. UTF-8 text in any language is not binary."""
        sample = content[:8192]
        if not sample:
            return False
        if b"\x00" in sample:
            return True
        try:
            codecs.getincrementaldecoder("utf-8")().decode(sample, final=False)
        except UnicodeDecodeError:
            pass
        else:
            return False
        control = sum(1 for b in sample if b < 32 and b not in (8, 9, 10, 12, 13, 27))
        return (control + sample.count(127)) / len(sample) > 0.10

    def _check_encoding(self, encoding: str) -> None:
        try:
            codecs.lookup(encoding)
        except LookupError as e:
            raise FilesystemError(
                f"Unknown text encoding: {encoding}", code="INVALID_ENCODING"
            ) from e

    def _decode(self, data: bytes, requested: str | None) -> tuple[str | None, str]:
        """Decode file bytes. Returns (None, 'base64') when the file is binary."""
        encoding = requested or self.config.default_encoding
        self._check_encoding(encoding)
        if requested:
            try:
                return data.decode(encoding), encoding
            except UnicodeDecodeError as e:
                raise FilesystemError(
                    f"Failed to decode file as {encoding}: {e}",
                    code="DECODE_ERROR",
                    details={"encoding": encoding},
                ) from e
        if data.startswith(codecs.BOM_UTF8):
            return data[len(codecs.BOM_UTF8) :].decode("utf-8", errors="replace"), "utf-8-sig"
        if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            try:
                return data.decode("utf-16"), "utf-16"
            except UnicodeDecodeError:
                pass
        if self._is_binary(data):
            return None, "base64"
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            # Legacy Windows text files, e.g. a '£' sign saved as cp1252
            return data.decode("cp1252", errors="replace"), "cp1252"

    def _ensure_writable(self) -> None:
        if self.config.read_only:
            raise FilesystemError(
                "Writing is switched off: the bridge is in read-only mode. An administrator "
                "can allow writing by setting FILE_BRIDGE_READ_ONLY=false.",
                code="READ_ONLY",
            )

    def _guard_bridge_dir(self, resolved: Path) -> None:
        parts = resolved.relative_to(self.root).parts
        if parts and parts[0].lower() == BRIDGE_DATA_DIR:
            raise SecurityError(
                f"The {BRIDGE_DATA_DIR} folder is managed by the bridge and cannot be changed."
            )

    def _backup(self, resolved: Path) -> str | None:
        """Copy an existing file to the versions folder before it is changed."""
        if not self.config.backup_on_write or not resolved.is_file():
            return None
        rel = resolved.relative_to(self.root)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        versions = self.root / BRIDGE_DATA_DIR / "versions"
        dest = versions / rel.parent / f"{rel.stem}.{stamp}{rel.suffix}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved, dest)
        return self._relative(dest)

    def _write_bytes(self, resolved: Path, data: bytes, *, atomic: bool) -> None:
        try:
            if not atomic:
                resolved.write_bytes(data)
                return
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=resolved.parent, delete=False, prefix=f".{resolved.name}.tmp."
            ) as tmp:
                tmp.write(data)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = Path(tmp.name)
            try:
                tmp_path.replace(resolved)
            except BaseException:
                tmp_path.unlink(missing_ok=True)
                raise
        except PermissionError as e:
            raise FilesystemError(
                "The file is open in another program or is read-only. Close it and try again.",
                code="FILE_LOCKED",
            ) from e

    # ---------------------------------------------------------------- tools

    def read_file(self, request: ReadFileRequest) -> ReadFileResponse:
        """Read a file safely."""
        resolved = self._resolve_path(request.path)

        log.info("read_file", path=request.path)

        if not resolved.exists():
            raise FilesystemError(f"File not found: {request.path}", code="NOT_FOUND")

        if not resolved.is_file():
            raise FilesystemError(f"Not a file: {request.path}", code="NOT_A_FILE")

        self._check_file_size(resolved, request.max_size)

        content_bytes = resolved.read_bytes()
        text, encoding = self._decode(content_bytes, request.encoding)

        if text is None:
            content = base64.b64encode(content_bytes).decode("ascii")
            log.warning("read_binary_file", path=request.path, size=len(content_bytes))
        else:
            content = text

        return ReadFileResponse(
            path=request.path,
            content=content,
            size=len(content_bytes),
            encoding=encoding,
            is_binary=text is None,
        )

    def write_file(self, request: WriteFileRequest) -> WriteFileResponse:
        """Write a file atomically, keeping a backup of any previous version."""
        self._ensure_writable()
        resolved = self._resolve_path(request.path)
        self._guard_bridge_dir(resolved)
        encoding = request.encoding or self.config.default_encoding
        self._check_encoding(encoding)

        log.info("write_file", path=request.path)

        try:
            content_bytes = request.content.encode(encoding)
        except UnicodeEncodeError as e:
            raise FilesystemError(
                f"The content cannot be saved as {encoding}: {e}", code="ENCODE_ERROR"
            ) from e

        if len(content_bytes) > self.config.max_file_size:
            raise FileSizeError(
                f"Content size {len(content_bytes)} bytes exceeds limit of "
                f"{self.config.max_file_size} bytes",
                details={"content_size": len(content_bytes), "limit": self.config.max_file_size},
            )

        if resolved.is_dir():
            raise FilesystemError(f"Not a file: {request.path}", code="NOT_A_FILE")

        if request.create_dirs:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        elif not resolved.parent.exists():
            raise FilesystemError(
                f"Parent directory does not exist: {Path(request.path).parent}",
                code="NOT_FOUND",
            )

        backup = self._backup(resolved)
        self._write_bytes(resolved, content_bytes, atomic=request.atomic)

        return WriteFileResponse(
            path=request.path, size=len(content_bytes), encoding=encoding, backup=backup
        )

    def list_dir(self, request: ListDirRequest) -> ListDirResponse:
        """List directory contents without ever leaving the root."""
        resolved = self._resolve_path(request.path)

        log.info("list_dir", path=request.path)

        if not resolved.exists():
            raise FilesystemError(f"Directory not found: {request.path}", code="NOT_FOUND")

        if not resolved.is_dir():
            raise FilesystemError(f"Not a directory: {request.path}", code="NOT_A_DIR")

        entries: list[DirEntry] = []
        max_levels = request.max_depth if request.recursive else 1

        def scan(current: Path, level: int) -> None:
            for entry in self._scandir(current):
                if entry.name == BRIDGE_DATA_DIR:
                    continue
                if not request.include_hidden and entry.name.startswith("."):
                    continue
                is_link, leaves_root = self._classify(entry)
                if leaves_root:
                    continue
                is_dir = _safe_is_dir(entry)
                if not request.glob_pattern or fnmatch.fnmatch(entry.name, request.glob_pattern):
                    entries.append(self._dir_entry(entry, is_dir=is_dir, is_link=is_link))
                if (
                    request.recursive
                    and is_dir
                    and not is_link
                    and (max_levels is None or level < max_levels)
                ):
                    scan(Path(entry.path), level + 1)

        scan(resolved, 1)

        return ListDirResponse(path=request.path, entries=entries, total=len(entries))

    def _dir_entry(self, entry: os.DirEntry[str], *, is_dir: bool, is_link: bool) -> DirEntry:
        size: int | None = None
        modified: float | None = None
        is_file = False
        try:
            stat = entry.stat()
            is_file = entry.is_file()
            size = stat.st_size if is_file else None
            modified = stat.st_mtime
        except OSError:
            pass  # broken link or file removed mid-listing
        return DirEntry(
            name=entry.name,
            path=self._relative(Path(entry.path)),
            is_dir=is_dir,
            is_file=is_file,
            is_symlink=is_link,
            size=size,
            modified=modified,
        )

    def search_files(self, request: SearchFilesRequest) -> SearchFilesResponse:
        """Search file contents using ripgrep."""
        resolved = self._resolve_path(request.path)

        log.info("search_files", pattern_length=len(request.pattern), path=request.path)

        if not resolved.exists():
            raise FilesystemError(f"Not found: {request.path}", code="NOT_FOUND")

        # --no-config stops a ripgrep config file changing behaviour; "-e" and "--"
        # make sure the pattern and path can never be read as ripgrep options.
        cmd = ["rg", "--json", "--line-number", "--no-config"]
        if not request.case_sensitive:
            cmd.append("-i")
        if request.fixed_strings:
            cmd.append("-F")
        if request.glob_pattern:
            cmd.extend(["-g", request.glob_pattern])
        if request.context_lines > 0:
            cmd.extend(["-C", str(request.context_lines)])
        cmd.extend(["-e", request.pattern, "--", str(resolved)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                stdin=subprocess.DEVNULL,  # never let rg read the MCP stdio channel
                timeout=_SEARCH_TIMEOUT_SECONDS,
                cwd=self.root,
            )
        except FileNotFoundError as e:
            raise FilesystemError(
                "ripgrep (rg) not found. Please install ripgrep.",
                code="MISSING_DEPENDENCY",
                details={"command": "rg"},
            ) from e
        except subprocess.TimeoutExpired as e:
            raise FilesystemError("Search timed out", code="TIMEOUT") from e

        stderr_lines = [
            line.replace(str(self.root), ".").strip()
            for line in result.stderr.decode("utf-8", errors="replace").splitlines()
            if line.strip()
        ]

        matches, truncated, saw_output = self._parse_rg(result.stdout, request)

        if result.returncode == 2 and not saw_output:
            reason = stderr_lines[0] if stderr_lines else "ripgrep reported an error"
            raise FilesystemError(f"Search failed: {reason}", code="SEARCH_ERROR")

        return SearchFilesResponse(
            pattern=request.pattern,
            path=request.path,
            matches=matches,
            total=len(matches),
            truncated=truncated,
            warnings=stderr_lines[:10] if result.returncode == 2 else [],
        )

    def _parse_rg(
        self, stdout: bytes, request: SearchFilesRequest
    ) -> tuple[list[SearchMatch], bool, bool]:
        matches: list[SearchMatch] = []
        truncated = False
        saw_output = False
        window = request.context_lines
        last: SearchMatch | None = None
        pending: list[tuple[int, str]] = []

        for raw in stdout.splitlines():
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            kind = message.get("type")
            data = message.get("data") or {}
            if kind == "begin":
                saw_output = True
                last, pending = None, []
                continue
            if kind not in ("match", "context"):
                continue
            line_no = data.get("line_number")
            if not isinstance(line_no, int):
                continue
            text = _rg_text(data.get("lines")).rstrip("\r\n")

            if kind == "context":
                if last is not None and 0 < line_no - last.line <= window:
                    last.context_after.append(text)
                pending.append((line_no, text))
                continue

            if len(matches) >= request.max_results:
                truncated = True
                break
            file_rel = self._display_path(_rg_text(data.get("path")))
            if file_rel is None:
                continue
            submatches = data.get("submatches") or []
            start = submatches[0].get("start") if submatches else None
            match = SearchMatch(
                file=file_rel,
                line=line_no,
                column=start + 1 if isinstance(start, int) else None,
                match=text,
                context_before=[t for (ln, t) in pending if 0 < line_no - ln <= window],
            )
            matches.append(match)
            last, pending = match, []

        return matches, truncated, saw_output

    def _display_path(self, path_text: str) -> str | None:
        path = Path(path_text)
        if not path.is_absolute():
            path = self.root / path
        if not _is_within(path, self.root):
            return None
        return self._relative(path)

    def glob(self, request: GlobRequest) -> GlobResponse:
        """Find files matching a glob pattern without ever leaving the root."""
        resolved = self._resolve_path(request.path)

        log.info("glob", pattern=request.pattern, path=request.path)

        if not resolved.exists() or not resolved.is_dir():
            raise FilesystemError(f"Directory not found: {request.path}", code="NOT_FOUND")

        pattern = request.pattern.replace("\\", "/").strip()
        if not pattern:
            raise FilesystemError("Glob pattern cannot be empty", code="INVALID_PATTERN")
        is_absolute = pattern.startswith("/") or re.match(r"^[A-Za-z]:", pattern)
        if is_absolute or ".." in pattern.split("/"):
            raise SecurityError("Glob patterns must be relative and may not contain '..'")
        if request.recursive and "**" not in pattern:
            pattern = f"**/{pattern}"
        regex = _glob_to_regex(pattern)

        matches: list[str] = []
        truncated = False
        for path, _is_dir in self._walk(resolved, include_hidden=request.include_hidden):
            if not regex.match(path.relative_to(resolved).as_posix()):
                continue
            if len(matches) >= request.max_results:
                truncated = True
                break
            matches.append(self._relative(path))

        return GlobResponse(
            pattern=request.pattern,
            path=request.path,
            matches=sorted(matches),
            total=len(matches),
            truncated=truncated,
        )

    def patch_file(self, request: PatchFileRequest) -> PatchFileResponse:
        """Replace exact text in a file, keeping its encoding and line endings."""
        self._ensure_writable()
        resolved = self._resolve_path(request.path)
        self._guard_bridge_dir(resolved)

        log.info("patch_file", path=request.path)

        if not resolved.exists():
            raise FilesystemError(f"File not found: {request.path}", code="NOT_FOUND")

        if not resolved.is_file():
            raise FilesystemError(f"Not a file: {request.path}", code="NOT_A_FILE")

        if not request.old_str:
            raise FilesystemError("Old string cannot be empty", code="PATCH_FAILED")

        self._check_file_size(resolved)
        data = resolved.read_bytes()
        text, encoding = self._decode(data, request.encoding)
        if text is None:
            raise FilesystemError(
                "This file is binary and cannot be patched as text", code="NOT_TEXT"
            )
        if encoding == "cp1252" and "�" in text:
            raise FilesystemError(
                "This file contains characters that cannot be rewritten safely", code="NOT_TEXT"
            )

        old, new = request.old_str, request.new_str
        count = text.count(old)
        # The AI usually sends '\n'; match files that use Windows line endings too.
        if count == 0 and "\r\n" in text and "\n" in old and "\r\n" not in old:
            crlf_old = old.replace("\n", "\r\n")
            if crlf_old in text:
                old = crlf_old
                new = new.replace("\r\n", "\n").replace("\n", "\r\n")
                count = text.count(old)

        if count == 0:
            raise FilesystemError(
                "Old string not found in file",
                code="PATCH_FAILED",
                details={"old_str_length": len(request.old_str)},
            )
        expected = request.expected_replacements
        if expected is not None and count != expected:
            raise FilesystemError(
                f"old_str appears {count} times but expected_replacements is {expected}. "
                "Include more surrounding text so it matches exactly, or set "
                f"expected_replacements to {count}.",
                code="PATCH_FAILED",
                details={"occurrences": count},
            )

        new_text = text.replace(old, new)
        try:
            new_bytes = new_text.encode(encoding)
        except UnicodeEncodeError as e:
            raise FilesystemError(
                f"The new text cannot be saved as {encoding}: {e}", code="ENCODE_ERROR"
            ) from e

        if len(new_bytes) > self.config.max_file_size:
            raise FileSizeError(
                f"Patched file size {len(new_bytes)} bytes exceeds limit of "
                f"{self.config.max_file_size} bytes",
                details={"new_size": len(new_bytes), "limit": self.config.max_file_size},
            )

        backup = self._backup(resolved)
        self._write_bytes(resolved, new_bytes, atomic=True)

        return PatchFileResponse(
            path=request.path,
            replacements=count,
            old_size=len(data),
            new_size=len(new_bytes),
            backup=backup,
        )
