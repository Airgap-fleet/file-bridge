"""MCP tool schemas and exports."""

try:
    from fastmcp import FastMCP  # FastMCP 4.x
except ImportError:
    from mcp.server.fastmcp import FastMCP  # FastMCP 3.x

app = FastMCP("FileSystem")

# Tool schema documentation
TOOLS_METADATA = {
    "fs_read": {
        "description": "Read file contents from a given path.",
        "parameters": {
            "path": "str - Path to the file to read (absolute or relative)",
            "max_bytes": "int - Maximum number of bytes to return. Use -1 for unlimited.",
        },
        "returns": "str - File contents truncated to max_bytes if needed, or complete content.",
    },
    "fs_write": {
        "description": "Write content to a file.",
        "parameters": {
            "path": "str - Absolute or relative path to the target file",
            "content": "str - Content to write to the new file",
        },
        "returns": "bool - True if write succeeded, False on error.",
    },
    "fs_list": {
        "description": "List files and directories at a given path.",
        "parameters": {"dir_path": "str - Directory path to list (empty for current directory)"},
        "returns": "list[str] - List of file and directory names at the path.",
    },
    "fs_glob": {
        "description": "Find files matching a glob pattern.",
        "parameters": {"pattern": "str - Glob pattern like *.py, **/*.md"},
        "returns": "list[str] - List of absolute paths to matching files.",
    },
}

# Re-export the app with all tools registered
__all__ = ["TOOLS_METADATA", "app"]
