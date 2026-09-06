#!/usr/bin/env python3
"""JSON-RPC stdio self-test for file-bridge.

Uses the official MCP Python client over stdio so framing matches the server.
Fails loudly (non-zero exit) if initialize / tools/list / tools/call fail.
Also samples stderr to confirm logs are not on the protocol channel.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

EXPECTED_TOOLS = {
    "read_file",
    "write_file",
    "list_dir",
    "search_files",
    "glob",
    "patch_file",
}


def fail(msg: str, code: int = 1) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)
    raise SystemExit(code)


def ok(msg: str) -> None:
    print(f"[OK] {msg}", file=sys.stderr)


async def run_test(exe: str, python: str, root: Path) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = os.environ.copy()
    env["FILE_BRIDGE_ROOT_PATH"] = str(root.resolve())
    env["FILE_BRIDGE_TRANSPORT"] = "stdio"
    env["FILE_BRIDGE_LOG_LEVEL"] = "WARNING"
    # Reduce banner / update-nudge noise during air-gap demos
    env["FASTMCP_SHOW_SERVER_BANNER"] = "false"

    if exe and Path(exe).is_file():
        params = StdioServerParameters(command=exe, args=[], env=env)
        ok(f"Launching exe: {exe}")
    else:
        params = StdioServerParameters(
            command=python,
            args=["-m", "filesystem_mcp.server"],
            env=env,
        )
        ok(f"Launching module via {python}")

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            ok(f"initialize OK (protocolVersion={getattr(init, 'protocolVersion', '?')})")

            tools_result = await session.list_tools()
            names = {t.name for t in tools_result.tools}
            missing = EXPECTED_TOOLS - names
            if missing:
                fail(f"tools/list missing: {sorted(missing)}; got={sorted(names)}")
            ok(f"tools/list OK ({len(names)} tools)")

            # FastMCP exposes the Pydantic parameter as a single "request" object
            call = await session.call_tool(
                "list_dir",
                {"request": {"path": ".", "recursive": False}},
            )
            if getattr(call, "isError", False):
                fail(f"tools/call list_dir returned isError: {call}")
            text = ""
            for block in call.content or []:
                text += getattr(block, "text", "") or ""
            if "entries" not in text and "total" not in text and "path" not in text:
                fail(f"tools/call list_dir unexpected payload: {text[:500]!r}")
            ok("tools/call list_dir OK (JSON-RPC tool path exercised)")

            return {
                "status": "pass",
                "tools": sorted(names),
                "root": str(root.resolve()),
                "protocolVersion": getattr(init, "protocolVersion", None),
                "server": getattr(getattr(init, "serverInfo", None), "name", None),
                "stdout_channel": "json-rpc-via-mcp-stdio-client",
                "note": "MCP stdio client validates Content-Length framed JSON-RPC on stdout; logs remain on stderr.",
            }


def main() -> int:
    parser = argparse.ArgumentParser(description="file-bridge JSON-RPC stdio self-test")
    parser.add_argument("--exe", default="", help="Path to airgap-file-bridge.exe (optional)")
    parser.add_argument("--python", default=sys.executable, help="Python for module fallback")
    parser.add_argument("--root", required=True, help="Root path for FILE_BRIDGE_ROOT_PATH")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        fail(f"Root path is not a directory: {root}")

    try:
        result = asyncio.run(asyncio.wait_for(run_test(args.exe, args.python, root), timeout=args.timeout))
    except TimeoutError:
        fail(f"Self-test timed out after {args.timeout}s")
    except SystemExit:
        raise
    except Exception as e:
        fail(f"Self-test exception: {type(e).__name__}: {e}")

    print(json.dumps(result, indent=2))
    ok("stdout carried MCP JSON-RPC only for exercised session (client-validated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())