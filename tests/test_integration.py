"""Integration tests for Filesystem MCP Server using FastMCP."""

import tempfile
from pathlib import Path

import pytest

from filesystem_mcp.core import FilesystemCore
from filesystem_mcp.models import (
    FilesystemConfig,
    GlobRequest,
    ListDirRequest,
    PatchFileRequest,
    ReadFileRequest,
    WriteFileRequest,
)
from filesystem_mcp.server import (
    glob,
    list_dir,
    patch_file,
    read_file,
    write_file,
)


class TestMCPServerIntegration:
    """Integration tests for the MCP server tools."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def core(self, temp_dir):
        """Create a FilesystemCore with test configuration."""
        config = FilesystemConfig(
            root_path=temp_dir,
            max_file_size=1024 * 1024,
            follow_symlinks=False,
            allow_absolute_paths=False,
            default_encoding="utf-8",
        )
        return FilesystemCore(config)

    @pytest.fixture(autouse=True)
    def inject_core(self, core):
        """Inject test core into server module by patching create_core."""
        import filesystem_mcp.server as server_module

        original_create_core = server_module.create_core
        original_get_core = server_module.get_core
        original_reset_core = server_module.reset_core

        def test_create_core():
            return core

        def test_get_core():
            return core

        def test_reset_core():
            pass

        server_module.create_core = test_create_core
        server_module.get_core = test_get_core
        server_module.reset_core = test_reset_core

        yield

        server_module.create_core = original_create_core
        server_module.get_core = original_get_core
        server_module.reset_core = original_reset_core

    @pytest.mark.asyncio
    async def test_read_file_tool(self, core, temp_dir):
        """Test read_file MCP tool."""
        test_file = temp_dir / "integration_read.txt"
        test_file.write_text("Integration test content")

        response = await read_file(ReadFileRequest(path="integration_read.txt"))

        assert response.path == "integration_read.txt"
        assert response.content == "Integration test content"
        assert response.size == 24
        assert response.is_binary is False

    @pytest.mark.asyncio
    async def test_write_file_tool(self, core, temp_dir):
        """Test write_file MCP tool."""
        response = await write_file(
            WriteFileRequest(path="integration_write.txt", content="Written via MCP")
        )

        assert response.path == "integration_write.txt"
        assert response.size == 15  # "Written via MCP" is 15 chars

        # Verify file exists
        assert (temp_dir / "integration_write.txt").read_text() == "Written via MCP"

    @pytest.mark.asyncio
    async def test_list_dir_tool(self, core, temp_dir):
        """Test list_dir MCP tool."""
        (temp_dir / "file1.txt").write_text("a")
        (temp_dir / "file2.py").write_text("b")
        (temp_dir / "subdir").mkdir()

        response = await list_dir(ListDirRequest(path="."))

        assert response.path == "."
        assert response.total == 3
        names = {e.name for e in response.entries}
        assert "file1.txt" in names
        assert "file2.py" in names
        assert "subdir" in names

    @pytest.mark.asyncio
    async def test_glob_tool(self, core, temp_dir):
        """Test glob MCP tool."""
        (temp_dir / "test.py").write_text("a")
        (temp_dir / "test.txt").write_text("b")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "test.py").write_text("c")

        response = await glob(GlobRequest(pattern="**/*.py", path="."))

        assert response.pattern == "**/*.py"
        assert response.total == 2
        matches = set(response.matches)
        assert "test.py" in matches
        # Handle both forward and backslash separators (Windows compatibility)
        assert any(m.replace("\\", "/") == "subdir/test.py" for m in matches)

    @pytest.mark.asyncio
    async def test_patch_file_tool(self, core, temp_dir):
        """Test patch_file MCP tool."""
        test_file = temp_dir / "integration_patch.txt"
        test_file.write_text("Hello world\nHello again")

        response = await patch_file(
            PatchFileRequest(path="integration_patch.txt", old_str="Hello", new_str="Hi")
        )

        assert response.path == "integration_patch.txt"
        assert response.replacements == 2

        content = test_file.read_text()
        assert content == "Hi world\nHi again"

    @pytest.mark.asyncio
    async def test_full_workflow(self, core, temp_dir):
        """Test a complete workflow: write, read, list, glob, patch."""
        # Write multiple files
        await write_file(
            WriteFileRequest(path="docs/readme.md", content="# Readme\n\nContent")
        )
        await write_file(
            WriteFileRequest(path="src/main.py", content="def main():\n    print('hello')")
        )
        await write_file(
            WriteFileRequest(path="src/utils.py", content="def util():\n    pass")
        )

        # List directory
        list_response = await list_dir(ListDirRequest(path=".", recursive=True))
        assert list_response.total >= 4  # docs, src, readme.md, main.py, utils.py

        # Glob for Python files
        glob_response = await glob(GlobRequest(pattern="**/*.py", path="."))
        assert glob_response.total == 2
        matches = {m.replace("\\", "/") for m in glob_response.matches}
        assert "src/main.py" in matches
        assert "src/utils.py" in matches

        # Read a file
        read_response = await read_file(ReadFileRequest(path="src/main.py"))
        assert "def main()" in read_response.content

        # Patch a file
        patch_response = await patch_file(
            PatchFileRequest(
                path="src/main.py", old_str="print('hello')", new_str="print('world')"
            )
        )
        assert patch_response.replacements == 1

        # Verify patch
        read_response = await read_file(ReadFileRequest(path="src/main.py"))
        assert "print('world')" in read_response.content
