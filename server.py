#!/usr/bin/env python3
"""
Filesystem MCP Server — FastMCP stdio transport
Tools: fs_read, fs_write, fs_list, fs_glob
"""

from mcp.server.fastmcp import FastMCP
from pathlib import Path
import os

mcp = FastMCP("filesystem-mcp")


@mcp.tool()
def fs_read(path: str, encoding: str = "utf-8") -> dict:
    """Read file content from path with optional encoding."""
    try:
        p = Path(path).resolve()
        if not p.exists():
            return {"error": f"File not found: {path}", "success": False}
        if not p.is_file():
            return {"error": f"Not a file: {path}", "success": False}
        content = p.read_text(encoding=encoding)
        return {"content": content, "success": True, "path": str(p)}
    except PermissionError:
        return {"error": f"Permission denied: {path}", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


@mcp.tool()
def fs_write(path: str, content: str, encoding: str = "utf-8", overwrite: bool = True) -> dict:
    """Write content to path with optional encoding/overwrite flags."""
    try:
        p = Path(path).resolve()
        if p.exists() and not overwrite:
            return {"error": f"File exists and overwrite=False: {path}", "success": False}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return {"success": True, "path": str(p), "bytes_written": len(content.encode(encoding))}
    except PermissionError:
        return {"error": f"Permission denied: {path}", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


@mcp.tool()
def fs_list(path: str, recursive: bool = False) -> dict:
    """List directory contents with optional recursive flag."""
    try:
        p = Path(path).resolve()
        if not p.exists():
            return {"error": f"Path not found: {path}", "success": False}
        if not p.is_dir():
            return {"error": f"Not a directory: {path}", "success": False}
        if recursive:
            entries = [{"path": str(e.relative_to(p)), "is_dir": e.is_dir(), "size": e.stat().st_size if e.is_file() else None} for e in p.rglob("*")]
        else:
            entries = [{"path": e.name, "is_dir": e.is_dir(), "size": e.stat().st_size if e.is_file() else None} for e in p.iterdir()]
        return {"entries": entries, "success": True, "path": str(p)}
    except PermissionError:
        return {"error": f"Permission denied: {path}", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


@mcp.tool()
def fs_glob(pattern: str, root: str = ".") -> dict:
    """Glob pattern matching for files/directories."""
    try:
        root_path = Path(root).resolve()
        if not root_path.exists():
            return {"error": f"Root not found: {root}", "success": False}
        matches = list(root_path.glob(pattern))
        entries = [{"path": str(m.relative_to(root_path)), "is_dir": m.is_dir(), "absolute": str(m)} for m in matches]
        return {"matches": entries, "success": True, "pattern": pattern, "root": str(root_path)}
    except PermissionError:
        return {"error": f"Permission denied: {root}", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


if __name__ == "__main__":
    mcp.run(transport="stdio")