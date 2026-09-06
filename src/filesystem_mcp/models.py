"""Pydantic models for Filesystem MCP Server tools."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _apply_legacy_env_prefix() -> None:
    """Map legacy FILESYSTEM_MCP_* env vars onto FILE_BRIDGE_* when unset.

    Older installs and .env files used FILESYSTEM_MCP_*. Canonical prefix is
    FILE_BRIDGE_* (product rename). Existing values are not overwritten.
    """
    legacy = "FILESYSTEM_MCP_"
    canonical = "FILE_BRIDGE_"
    for key, value in list(os.environ.items()):
        if not key.startswith(legacy):
            continue
        new_key = canonical + key[len(legacy) :]
        if new_key not in os.environ:
            os.environ[new_key] = value


_apply_legacy_env_prefix()

class FilesystemConfig(BaseSettings):
    """Configuration for the Filesystem MCP Server."""

    model_config = SettingsConfigDict(
        env_prefix="FILE_BRIDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **data: Any) -> None:
        """Apply legacy env aliases, then load settings."""
        _apply_legacy_env_prefix()
        super().__init__(**data)


    root_path: Path = Field(
        default=Path.cwd(),
        description=(
            "Root directory for all filesystem operations. All paths are resolved relative to this."
        ),
    )
    max_file_size: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        ge=1024,
        le=1024 * 1024 * 1024,  # 1 GB max
        description="Maximum file size for read/write operations in bytes.",
    )
    follow_symlinks: bool = Field(
        default=False,
        description=(
            "Whether to follow symlinks. When false, symlinks are treated as regular files."
        ),
    )
    allow_absolute_paths: bool = Field(
        default=False,
        description=(
            "Whether to allow absolute paths in tool calls. "
            "When false, all paths must be relative to root_path."
        ),
    )
    default_encoding: str = Field(
        default="utf-8",
        description="Default text encoding for read/write operations.",
    )

    @field_validator("root_path", mode="before")
    @classmethod
    def resolve_root_path(cls, v: str | Path) -> Path:
        """Resolve the root path to absolute."""
        return Path(v).expanduser().resolve()


class ReadFileRequest(BaseModel):
    """Request model for read_file tool."""

    path: str = Field(description="Path to the file to read, relative to root.")
    encoding: str | None = Field(
        default=None,
        description="Text encoding to use. Defaults to config default_encoding.",
    )
    max_size: int | None = Field(
        default=None,
        ge=1,
        description="Override max file size for this read operation.",
    )


class ReadFileResponse(BaseModel):
    """Response model for read_file tool."""

    path: str = Field(description="The path that was read.")
    content: str = Field(description="File content as text.")
    size: int = Field(description="File size in bytes.")
    encoding: str = Field(description="Encoding used to read the file.")
    is_binary: bool = Field(description="Whether the file was detected as binary.")


class WriteFileRequest(BaseModel):
    """Request model for write_file tool."""

    path: str = Field(description="Path to the file to write, relative to root.")
    content: str = Field(description="Content to write to the file.")
    encoding: str | None = Field(
        default=None,
        description="Text encoding to use. Defaults to config default_encoding.",
    )
    create_dirs: bool = Field(
        default=True,
        description="Create parent directories if they don't exist.",
    )
    atomic: bool = Field(
        default=True,
        description="Write atomically using a temporary file and rename.",
    )


class WriteFileResponse(BaseModel):
    """Response model for write_file tool."""

    path: str = Field(description="The path that was written.")
    size: int = Field(description="Number of bytes written.")
    encoding: str = Field(description="Encoding used to write the file.")


class ListDirRequest(BaseModel):
    """Request model for list_dir tool."""

    path: str = Field(default=".", description="Directory path to list, relative to root.")
    glob_pattern: str | None = Field(
        default=None,
        description="Optional glob pattern to filter entries (e.g., '*.py').",
    )
    recursive: bool = Field(
        default=False,
        description="Whether to list recursively.",
    )
    include_hidden: bool = Field(
        default=False,
        description="Whether to include hidden files (starting with '.').",
    )
    max_depth: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum recursion depth when recursive=True.",
    )


class DirEntry(BaseModel):
    """A single directory entry."""

    name: str = Field(description="Entry name (basename).")
    path: str = Field(description="Full path relative to root.")
    is_dir: bool = Field(description="Whether this is a directory.")
    is_file: bool = Field(description="Whether this is a regular file.")
    is_symlink: bool = Field(description="Whether this is a symlink.")
    size: int | None = Field(default=None, description="File size in bytes (None for dirs).")
    modified: float | None = Field(
        default=None, description="Last modified timestamp (Unix epoch)."
    )


class ListDirResponse(BaseModel):
    """Response model for list_dir tool."""

    path: str = Field(description="The directory path that was listed.")
    entries: list[DirEntry] = Field(description="List of directory entries.")
    total: int = Field(description="Total number of entries returned.")


class SearchFilesRequest(BaseModel):
    """Request model for search_files tool."""

    pattern: str = Field(description="Search pattern (ripgrep-compatible regex).")
    path: str = Field(default=".", description="Directory to search in, relative to root.")
    glob_pattern: str | None = Field(
        default=None,
        description="Optional glob pattern to filter files (e.g., '*.py').",
    )
    case_sensitive: bool = Field(
        default=True,
        description="Whether the search is case-sensitive.",
    )
    max_results: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of results to return.",
    )
    context_lines: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of context lines around each match.",
    )


class SearchMatch(BaseModel):
    """A single search match."""

    file: str = Field(description="Path to the file containing the match, relative to root.")
    line: int = Field(description="Line number of the match (1-indexed).")
    column: int | None = Field(default=None, description="Column number of the match (1-indexed).")
    match: str = Field(description="The matched text.")
    context_before: list[str] = Field(default_factory=list, description="Lines before the match.")
    context_after: list[str] = Field(default_factory=list, description="Lines after the match.")


class SearchFilesResponse(BaseModel):
    """Response model for search_files tool."""

    pattern: str = Field(description="The search pattern used.")
    path: str = Field(description="The directory that was searched.")
    matches: list[SearchMatch] = Field(description="List of matches found.")
    total: int = Field(description="Total number of matches found.")
    truncated: bool = Field(description="Whether results were truncated due to max_results.")


class GlobRequest(BaseModel):
    """Request model for glob tool."""

    pattern: str = Field(description="Glob pattern to match (e.g., '**/*.py').")
    path: str = Field(default=".", description="Directory to search in, relative to root.")
    recursive: bool = Field(
        default=True,
        description="Whether to search recursively (only matters for patterns without **).",
    )
    include_hidden: bool = Field(
        default=False,
        description="Whether to include hidden files.",
    )
    max_results: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of results to return.",
    )


class GlobResponse(BaseModel):
    """Response model for glob tool."""

    pattern: str = Field(description="The glob pattern used.")
    path: str = Field(description="The directory that was searched.")
    matches: list[str] = Field(description="List of matching paths relative to root.")
    total: int = Field(description="Total number of matches found.")
    truncated: bool = Field(description="Whether results were truncated due to max_results.")


class PatchFileRequest(BaseModel):
    """Request model for patch_file tool."""

    path: str = Field(description="Path to the file to patch, relative to root.")
    old_str: str = Field(description="The exact string to find and replace.")
    new_str: str = Field(description="The string to replace it with.")
    encoding: str | None = Field(
        default=None,
        description="Text encoding to use. Defaults to config default_encoding.",
    )


class PatchFileResponse(BaseModel):
    """Response model for patch_file tool."""

    path: str = Field(description="The path that was patched.")
    replacements: int = Field(description="Number of replacements made.")
    old_size: int = Field(description="File size before patch in bytes.")
    new_size: int = Field(description="File size after patch in bytes.")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(description="Error type/code.")
    message: str = Field(description="Human-readable error message.")
    details: dict[str, Any] | None = Field(default=None, description="Additional error details.")
