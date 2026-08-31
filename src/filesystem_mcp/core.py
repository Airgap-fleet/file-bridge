"""Core business logic for Filesystem MCP Server.

This module contains all filesystem operations without any FastMCP dependencies,
making it fully testable in isolation.
"""

import subprocess
from pathlib import Path
from typing import Any

import structlog

from filesystem_mcp.models import (
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


class FilesystemCore:
    """Core filesystem operations - no FastMCP dependencies."""

    def __init__(self, config: FilesystemConfig | None = None):
        self.config = config or FilesystemConfig()
        log.info("filesystem_core_initialized", root_path=str(self.config.root_path))

    def _resolve_path(self, path: str) -> Path:
            """Resolve a user-provided path to an absolute path within the root."""
            # Handle absolute paths
            if Path(path).is_absolute():
                if not self.config.allow_absolute_paths:
                    raise SecurityError(
                        "Absolute paths are not allowed (allow_absolute_paths=False)",
                        details={"path": path},
                    )
                resolved = Path(path).resolve()
            else:
                # Relative to root
                resolved = (self.config.root_path / path).resolve()

            # Security: ensure the resolved path is within root
            try:
                resolved.relative_to(self.config.root_path)
            except ValueError as e:
                raise SecurityError(
                    f"Path '{path}' resolves outside the configured root directory",
                    details={
                        "requested_path": path,
                        "resolved_path": str(resolved),
                        "root_path": str(self.config.root_path),
                    },
                ) from e

            # Security: symlink protection - check original path components BEFORE resolving
            if not self.config.follow_symlinks:
                # Build path incrementally from root and check each component for symlinks
                # Use the original relative path, not the resolved one
                check_path = self.config.root_path
                for part in Path(path).parts:
                    check_path = check_path / part
                    if check_path.is_symlink():
                        raise SecurityError(
                            "Symlinks are not allowed (follow_symlinks=False)",
                            details={"path": str(check_path)},
                        )

            return resolved

    def _check_file_size(self, path: Path, max_size: int | None = None) -> None:
        """Check if file size is within limits."""
        limit = max_size or self.config.max_file_size
        if path.exists() and path.is_file():
            size = path.stat().st_size
            if size > limit:
                raise FileSizeError(
                    f"File size {size} bytes exceeds limit of {limit} bytes",
                    details={"file_size": size, "limit": limit, "path": str(path)},
                )

    def _is_binary(self, content: bytes) -> bool:
        """Heuristic to detect binary files."""
        if b"\x00" in content:
            return True
        # Check for high ratio of non-printable characters
        if len(content) > 0:
            printable = sum(1 for b in content[:8192] if 32 <= b <= 126 or b in (9, 10, 13))
            if printable / min(len(content), 8192) < 0.7:
                return True
        return False

    def read_file(self, request: ReadFileRequest) -> ReadFileResponse:
        """Read a file safely."""
        resolved = self._resolve_path(request.path)
        encoding = request.encoding or self.config.default_encoding

        log.info("read_file", path=request.path, resolved=str(resolved))

        if not resolved.exists():
            raise FilesystemError(f"File not found: {request.path}", code="NOT_FOUND")

        if not resolved.is_file():
            raise FilesystemError(f"Not a file: {request.path}", code="NOT_A_FILE")

        self._check_file_size(resolved, request.max_size)

        # Read as bytes first to detect binary
        content_bytes = resolved.read_bytes()
        is_binary = self._is_binary(content_bytes)

        if is_binary:
            # For binary files, return base64 or hex representation
            import base64

            content = base64.b64encode(content_bytes).decode("ascii")
            log.warning("read_binary_file", path=request.path, size=len(content_bytes))
        else:
            try:
                content = content_bytes.decode(encoding)
            except UnicodeDecodeError as e:
                raise FilesystemError(
                    f"Failed to decode file as {encoding}: {e}",
                    code="DECODE_ERROR",
                    details={"encoding": encoding},
                ) from e

        return ReadFileResponse(
            path=request.path,
            content=content,
            size=len(content_bytes),
            encoding=encoding,
            is_binary=is_binary,
        )

    def write_file(self, request: WriteFileRequest) -> WriteFileResponse:
        """Write a file atomically."""
        resolved = self._resolve_path(request.path)
        encoding = request.encoding or self.config.default_encoding

        log.info("write_file", path=request.path, resolved=str(resolved))

        # Create parent directories
        if request.create_dirs:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        elif not resolved.parent.exists():
            raise FilesystemError(
                f"Parent directory does not exist: {resolved.parent}",
                code="NOT_FOUND",
            )

        content_bytes = request.content.encode(encoding)

        # Check size limit BEFORE writing
        if len(content_bytes) > self.config.max_file_size:
            raise FileSizeError(
                "Content size "
                f"{len(content_bytes)} bytes exceeds limit of "
                f"{self.config.max_file_size} bytes",
                details={
                    "content_size": len(content_bytes),
                    "limit": self.config.max_file_size,
                },
            )

        if request.atomic:
            # Atomic write: write to temp file then rename
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="wb", dir=resolved.parent, delete=False, prefix=f".{resolved.name}.tmp."
            ) as tmp:
                tmp.write(content_bytes)
                tmp_path = Path(tmp.name)
            try:
                tmp_path.replace(resolved)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise
        else:
            resolved.write_bytes(content_bytes)

        return WriteFileResponse(
            path=request.path,
            size=len(content_bytes),
            encoding=encoding,
        )

    def list_dir(self, request: ListDirRequest) -> ListDirResponse:
        """List directory contents."""
        resolved = self._resolve_path(request.path)

        log.info("list_dir", path=request.path, resolved=str(resolved))

        if not resolved.exists():
            raise FilesystemError(f"Directory not found: {request.path}", code="NOT_FOUND")

        if not resolved.is_dir():
            raise FilesystemError(f"Not a directory: {request.path}", code="NOT_A_DIR")

        entries: list[DirEntry] = []

        def scan_dir(current: Path, depth: int = 0) -> None:
            if request.max_depth is not None and depth > request.max_depth:
                return

            try:
                for entry in sorted(
                    current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())
                ):
                    # Skip hidden files unless requested
                    if not request.include_hidden and entry.name.startswith("."):
                        continue

                    # Apply glob filter if provided
                    if request.glob_pattern:
                        import fnmatch

                        if not fnmatch.fnmatch(entry.name, request.glob_pattern):
                            if not entry.is_dir() or not request.recursive:
                                continue

                    stat = entry.stat()
                    entries.append(
                        DirEntry(
                            name=entry.name,
                            path=str(entry.relative_to(self.config.root_path)),
                            is_dir=entry.is_dir(),
                            is_file=entry.is_file(),
                            is_symlink=entry.is_symlink(),
                            size=stat.st_size if entry.is_file() else None,
                            modified=stat.st_mtime,
                        )
                    )

                    # Recurse into subdirectories
                    if request.recursive and entry.is_dir() and not entry.is_symlink():
                        scan_dir(entry, depth + 1)
            except PermissionError:
                log.warning("permission_denied_listing", path=str(current))

        scan_dir(resolved)

        return ListDirResponse(
            path=request.path,
            entries=entries,
            total=len(entries),
        )

    def search_files(self, request: SearchFilesRequest) -> SearchFilesResponse:
        """Search file contents using ripgrep."""
        resolved = self._resolve_path(request.path)

        log.info("search_files", pattern=request.pattern, path=request.path, resolved=str(resolved))

        if not resolved.exists() or not resolved.is_dir():
            raise FilesystemError(f"Directory not found: {request.path}", code="NOT_FOUND")

        # Build ripgrep command
        cmd = ["rg", "--json", "--no-heading", "--line-number"]

        if not request.case_sensitive:
            cmd.append("-i")

        if request.glob_pattern:
            cmd.extend(["-g", request.glob_pattern])

        if request.context_lines > 0:
            cmd.extend(["-B", str(request.context_lines), "-A", str(request.context_lines)])

        cmd.extend([request.pattern, str(resolved)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.config.root_path,
            )
        except FileNotFoundError as e:
            raise FilesystemError(
                "ripgrep (rg) not found. Please install ripgrep.",
                code="MISSING_DEPENDENCY",
                details={"command": "rg"},
            ) from e
        except subprocess.TimeoutExpired as e:
            raise FilesystemError("Search timed out", code="TIMEOUT") from e

        matches: list[SearchMatch] = []
        truncated = False

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            if len(matches) >= request.max_results:
                truncated = True
                break

            try:
                import json

                data = json.loads(line)
                if data.get("type") == "match":
                    match_data = data["data"]
                    matches.append(
                        SearchMatch(
                            file=match_data["path"]["text"],
                            line=match_data["line_number"],
                            column=match_data.get("submatches", [{}])[0].get("start"),
                            match=match_data["lines"]["text"].rstrip("\n"),
                            context_before=[],  # Would need context parsing
                            context_after=[],
                        )
                    )
            except json.JSONDecodeError:
                continue

        return SearchFilesResponse(
            pattern=request.pattern,
            path=request.path,
            matches=matches,
            total=len(matches),
            truncated=truncated,
        )

    def glob(self, request: GlobRequest) -> GlobResponse:
        """Find files matching a glob pattern."""
        resolved = self._resolve_path(request.path)

        log.info("glob", pattern=request.pattern, path=request.path, resolved=str(resolved))

        if not resolved.exists() or not resolved.is_dir():
            raise FilesystemError(f"Directory not found: {request.path}", code="NOT_FOUND")

        matches: list[str] = []

        # Use pathlib's glob
        if request.recursive and "**" not in request.pattern:
            pattern = f"**/{request.pattern}"
        else:
            pattern = request.pattern

        for match in resolved.glob(pattern):
            # Skip hidden unless requested
            if not request.include_hidden:
                if any(part.startswith(".") for part in match.relative_to(resolved).parts):
                    continue

            rel_path = match.relative_to(self.config.root_path)
            matches.append(str(rel_path))

            if len(matches) >= request.max_results:
                break

        truncated = len(matches) >= request.max_results

        return GlobResponse(
            pattern=request.pattern,
            path=request.path,
            matches=sorted(matches),
            total=len(matches),
            truncated=truncated,
        )

    def patch_file(self, request: PatchFileRequest) -> PatchFileResponse:
        """Apply a targeted patch to a file."""
        resolved = self._resolve_path(request.path)
        encoding = request.encoding or self.config.default_encoding

        log.info("patch_file", path=request.path, resolved=str(resolved))

        if not resolved.exists():
            raise FilesystemError(f"File not found: {request.path}", code="NOT_FOUND")

        if not resolved.is_file():
            raise FilesystemError(f"Not a file: {request.path}", code="NOT_A_FILE")

        if not request.old_str:
            raise FilesystemError("Old string cannot be empty", code="PATCH_FAILED")

        old_content = resolved.read_text(encoding=encoding)
        old_size = len(old_content.encode(encoding))

        if request.old_str not in old_content:
            raise FilesystemError(
                "Old string not found in file",
                code="PATCH_FAILED",
                details={"old_str_length": len(request.old_str)},
            )

        new_content = old_content.replace(request.old_str, request.new_str)
        replacements = old_content.count(request.old_str)
        new_size = len(new_content.encode(encoding))

        # Check size limit
        if new_size > self.config.max_file_size:
            raise FileSizeError(
                "Patched file size "
                f"{new_size} bytes exceeds limit of "
                f"{self.config.max_file_size} bytes",
                details={"new_size": new_size, "limit": self.config.max_file_size},
            )

        # Atomic write
        import tempfile

        tmp_prefix = f".{resolved.name}.tmp."
        with tempfile.NamedTemporaryFile(
            mode="w", encoding=encoding, dir=resolved.parent, delete=False, prefix=tmp_prefix
        ) as tmp:
            tmp.write(new_content)
            tmp_path = Path(tmp.name)
        try:
            tmp_path.replace(resolved)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        return PatchFileResponse(
            path=request.path,
            replacements=replacements,
            old_size=old_size,
            new_size=new_size,
        )
