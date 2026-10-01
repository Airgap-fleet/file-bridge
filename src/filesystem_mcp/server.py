"""Filesystem MCP Server — FastMCP application with registered tools."""

import argparse
import logging
import sys
from collections.abc import Callable
from typing import TypeVar

import anyio
import structlog
from fastmcp import FastMCP

from filesystem_mcp._version import __version__
from filesystem_mcp.core import FilesystemCore, FilesystemError
from filesystem_mcp.models import (
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
    WriteFileRequest,
    WriteFileResponse,
)

log = structlog.get_logger()

T = TypeVar("T")

# Global core instance (can be replaced for testing)
_core: FilesystemCore | None = None


def get_core() -> FilesystemCore:
    """Get the global FilesystemCore instance, creating it if needed."""
    global _core
    if _core is None:
        config = FilesystemConfig()
        _core = FilesystemCore(config)
    return _core


def set_core(core: FilesystemCore) -> None:
    """Replace the global core instance (for testing)."""
    global _core
    _core = core


def reset_core() -> None:
    """Reset the global core to default (for testing cleanup)."""
    global _core
    _core = None


def create_core() -> FilesystemCore:
    """Create a fresh FilesystemCore instance (for testing)."""
    return FilesystemCore(FilesystemConfig())


async def _in_thread(fn: Callable[[], T]) -> T:
    """Run blocking file work off the event loop so the stdio session stays responsive."""
    return await anyio.to_thread.run_sync(fn)


# Create FastMCP app
mcp = FastMCP("airgap-file-bridge")


@mcp.tool()
async def read_file(request: ReadFileRequest) -> ReadFileResponse:
    """Read a file from the filesystem.

    Returns the file content as text. Binary files are returned as base64-encoded strings
    with `is_binary=True`. Supports configurable size limits and encoding.
    """
    log.info("tool_read_file", path=request.path)
    core = get_core()
    return await _in_thread(lambda: core.read_file(request))


@mcp.tool()
async def write_file(request: WriteFileRequest) -> WriteFileResponse:
    """Write content to a file atomically.

    Refused while the bridge is in read-only mode (the default). The previous version of
    an existing file is kept under .file-bridge/versions. Creates parent directories by
    default.
    """
    log.info("tool_write_file", path=request.path, size=len(request.content))
    core = get_core()
    return await _in_thread(lambda: core.write_file(request))


@mcp.tool()
async def list_dir(request: ListDirRequest) -> ListDirResponse:
    """List directory contents with optional filtering.

    Supports glob pattern filtering, recursive listing, hidden file inclusion,
    and configurable recursion depth.
    """
    log.info("tool_list_dir", path=request.path, recursive=request.recursive)
    core = get_core()
    return await _in_thread(lambda: core.list_dir(request))


@mcp.tool()
async def search_files(request: SearchFilesRequest) -> SearchFilesResponse:
    """Search file contents using ripgrep (rg).

    Requires ripgrep to be installed on the system. Supports regex or plain-text patterns,
    glob filtering, case sensitivity, context lines, and result limiting.
    """
    log.info("tool_search_files", pattern_length=len(request.pattern), path=request.path)
    core = get_core()
    return await _in_thread(lambda: core.search_files(request))


@mcp.tool()
async def glob(request: GlobRequest) -> GlobResponse:
    """Find files matching a glob pattern.

    Supports recursive patterns (**), hidden file filtering, and result limiting.
    Patterns must be relative and may not contain '..'.
    """
    log.info("tool_glob", pattern=request.pattern, path=request.path)
    core = get_core()
    return await _in_thread(lambda: core.glob(request))


@mcp.tool()
async def patch_file(request: PatchFileRequest) -> PatchFileResponse:
    """Replace exact text in a file.

    By default old_str must appear exactly once (set expected_replacements to change
    this). Keeps the file's encoding and line endings, writes atomically, and keeps the
    previous version under .file-bridge/versions. Refused in read-only mode (the default).
    """
    log.info(
        "tool_patch_file",
        path=request.path,
        old_len=len(request.old_str),
        new_len=len(request.new_str),
    )
    core = get_core()
    return await _in_thread(lambda: core.patch_file(request))


def configure_logging(level: int = logging.INFO) -> None:
    """Send all structured logs to stderr so stdio JSON-RPC stays clean."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
        force=True,
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def _log_level(name: str) -> int:
    level = logging.getLevelName(name.strip().upper())
    return level if isinstance(level, int) else logging.INFO


def main(argv: list[str] | None = None) -> None:
    """Entry point for the MCP server."""
    parser = argparse.ArgumentParser(
        prog="airgap-file-bridge",
        description=(
            "Local MCP server that lets an AI assistant work inside one folder. "
            "Configure it with FILE_BRIDGE_* environment variables; it talks over stdio."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--check", action="store_true", help="check the configuration, print the result and exit"
    )
    args = parser.parse_args(argv)

    config = FilesystemConfig()
    configure_logging(_log_level(config.log_level))

    try:
        core = FilesystemCore(config)
    except FilesystemError as e:
        sys.stderr.write(f"File Bridge cannot start: {e.message}\n")
        raise SystemExit(2) from e
    set_core(core)

    if args.check:
        mode = "read-only" if config.read_only else "read and write"
        sys.stdout.write(f"OK: File Bridge {__version__} is set up for {core.root} ({mode}).\n")
        return

    log.info(
        "starting_file_bridge",
        version=__version__,
        root_path=str(core.root),
        read_only=config.read_only,
    )

    # Run the FastMCP server (stdio transport)
    mcp.run(show_banner=False)


if __name__ == "__main__":
    main()
