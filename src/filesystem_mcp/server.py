"""Filesystem MCP Server — FastMCP application with registered tools."""

import structlog
from fastmcp import FastMCP

from filesystem_mcp.core import FilesystemCore
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


# Create FastMCP app
mcp = FastMCP("filesystem-mcp")


@mcp.tool()
async def read_file(request: ReadFileRequest) -> ReadFileResponse:
    """Read a file from the filesystem.

    Returns the file content as text. Binary files are returned as base64-encoded strings
    with `is_binary=True`. Supports configurable size limits and encoding.
    """
    log.info("tool_read_file", path=request.path)
    return get_core().read_file(request)


@mcp.tool()
async def write_file(request: WriteFileRequest) -> WriteFileResponse:
    """Write content to a file atomically.

    Creates parent directories by default. Uses atomic write (temp file + rename) by default
    to prevent partial writes. Supports configurable encoding.
    """
    log.info("tool_write_file", path=request.path, size=len(request.content))
    return get_core().write_file(request)


@mcp.tool()
async def list_dir(request: ListDirRequest) -> ListDirResponse:
    """List directory contents with optional filtering.

    Supports glob pattern filtering, recursive listing, hidden file inclusion,
    and configurable recursion depth.
    """
    log.info("tool_list_dir", path=request.path, recursive=request.recursive)
    return get_core().list_dir(request)


@mcp.tool()
async def search_files(request: SearchFilesRequest) -> SearchFilesResponse:
    """Search file contents using ripgrep (rg).

    Requires ripgrep to be installed on the system. Supports regex patterns,
    glob filtering, case sensitivity, context lines, and result limiting.
    """
    log.info("tool_search_files", pattern=request.pattern, path=request.path)
    return get_core().search_files(request)


@mcp.tool()
async def glob(request: GlobRequest) -> GlobResponse:
    """Find files matching a glob pattern.

    Uses pathlib's glob matching. Supports recursive patterns (**), hidden file
    filtering, and result limiting.
    """
    log.info("tool_glob", pattern=request.pattern, path=request.path)
    return get_core().glob(request)


@mcp.tool()
async def patch_file(request: PatchFileRequest) -> PatchFileResponse:
    """Apply a targeted patch to a file.

    Finds all occurrences of `old_str` and replaces them with `new_str`.
    Uses atomic write. Returns the number of replacements made.
    """
    log.info(
        "tool_patch_file",
        path=request.path,
        old_len=len(request.old_str),
        new_len=len(request.new_str),
    )
    return get_core().patch_file(request)


def main() -> None:
    """Entry point for the MCP server."""

    # Configure structlog for JSON output to stderr
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    )

    log.info("starting_filesystem_mcp", version="0.1.0", root_path=str(get_core().config.root_path))

    # Run the FastMCP server (stdio transport by default)
    mcp.run()


if __name__ == "__main__":
    main()
