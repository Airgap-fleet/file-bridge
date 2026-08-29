"""Unit tests for FilesystemCore."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from filesystem_mcp.core import (
    FileSizeError,
    FilesystemCore,
    FilesystemError,
    SecurityError,
)
from filesystem_mcp.models import FilesystemConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def config(temp_dir):
    """Create a test configuration."""
    return FilesystemConfig(root_path=temp_dir, max_file_size=1024 * 1024)  # 1 MB


@pytest.fixture
def core(config):
    """Create a FilesystemCore instance."""
    return FilesystemCore(config)


class TestFilesystemCore:
    """Tests for FilesystemCore class."""

    def test_init(self, core, temp_dir):
        """Test initialization."""
        assert core.config.root_path == temp_dir

    def test_resolve_path_relative(self, core, temp_dir):
        """Test resolving relative paths."""
        resolved = core._resolve_path("test.txt")
        assert resolved == (temp_dir / "test.txt").resolve()

    def test_resolve_path_absolute_not_allowed(self, core):
        """Test that absolute paths are rejected when not allowed."""
        with pytest.raises(SecurityError) as exc:
            core._resolve_path("/etc/passwd")
        assert exc.value.code == "SECURITY_ERROR"

    def test_resolve_path_absolute_allowed(self, temp_dir):
        """Test absolute paths when allowed."""
        config = FilesystemConfig(root_path=temp_dir, allow_absolute_paths=True)
        core = FilesystemCore(config)
        resolved = core._resolve_path(str(temp_dir / "test.txt"))
        assert resolved == (temp_dir / "test.txt").resolve()

    def test_resolve_path_outside_root(self, core, temp_dir):
        """Test that paths outside root are rejected."""
        # Create a subdirectory
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        with pytest.raises(SecurityError) as exc:
            core._resolve_path("../etc/passwd")
        assert exc.value.code == "SECURITY_ERROR"

    def test_read_file_success(self, core, temp_dir):
        """Test reading a file successfully."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        from filesystem_mcp.models import ReadFileRequest

        request = ReadFileRequest(path="test.txt")
        response = core.read_file(request)

        assert response.content == "Hello, World!"
        assert response.size == 13
        assert response.is_binary is False

    def test_read_file_not_found(self, core):
        """Test reading a non-existent file."""
        from filesystem_mcp.models import ReadFileRequest

        request = ReadFileRequest(path="nonexistent.txt")
        with pytest.raises(FilesystemError) as exc:
            core.read_file(request)
        assert exc.value.code == "NOT_FOUND"

    def test_read_file_not_a_file(self, core, _temp_dir):
            """Test reading a directory as a file."""
            from filesystem_mcp.models import ReadFileRequest

            request = ReadFileRequest(path=".")
            with pytest.raises(FilesystemError) as exc:
                core.read_file(request)
            assert exc.value.code == "NOT_A_FILE"

    def test_read_file_size_limit(self, core, temp_dir):
        """Test file size limit on read."""
        test_file = temp_dir / "large.txt"
        test_file.write_text("x" * 2000)  # 2KB

        from filesystem_mcp.models import ReadFileRequest

        request = ReadFileRequest(path="large.txt", max_size=1000)  # 1KB limit
        with pytest.raises(FileSizeError):
            core.read_file(request)

    def test_write_file_success(self, core, temp_dir):
        """Test writing a file successfully."""
        from filesystem_mcp.models import WriteFileRequest

        request = WriteFileRequest(path="new.txt", content="New content")
        response = core.write_file(request)

        assert response.size == 11
        assert (temp_dir / "new.txt").read_text() == "New content"

    def test_write_file_atomic(self, core, temp_dir):
        """Test atomic write."""
        from filesystem_mcp.models import WriteFileRequest

        request = WriteFileRequest(path="atomic.txt", content="Atomic write", atomic=True)
        response = core.write_file(request)

        assert response.size == 12
        assert (temp_dir / "atomic.txt").read_text() == "Atomic write"

    def test_write_file_size_limit(self, core):
        """Test file size limit on write."""
        from filesystem_mcp.models import WriteFileRequest

        # Create a core with small limit for this test (minimum 1024)
        small_config = FilesystemConfig(root_path=core.config.root_path, max_file_size=1024)
        small_core = FilesystemCore(small_config)

        request = WriteFileRequest(path="large.txt", content="x" * 2000)
        with pytest.raises(FileSizeError):
            small_core.write_file(request)

    def test_write_file_create_dirs(self, core, temp_dir):
        """Test writing with create_dirs=True."""
        from filesystem_mcp.models import WriteFileRequest

        request = WriteFileRequest(path="subdir/new.txt", content="In subdir", create_dirs=True)
        response = core.write_file(request)

        assert response.size == 9
        assert (temp_dir / "subdir" / "new.txt").read_text() == "In subdir"

    def test_write_file_no_create_dirs_fail(self, core):
        """Test writing without create_dirs fails when parent doesn't exist."""
        from filesystem_mcp.models import WriteFileRequest

        request = WriteFileRequest(path="nonexistent/new.txt", content="Fail", create_dirs=False)
        with pytest.raises(FilesystemError) as exc:
            core.write_file(request)
        assert exc.value.code == "NOT_FOUND"

    def test_list_dir_success(self, core, temp_dir):
        """Test listing a directory."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "subdir").mkdir()

        from filesystem_mcp.models import ListDirRequest

        request = ListDirRequest(path=".")
        response = core.list_dir(request)

        assert response.total == 3
        names = [e.name for e in response.entries]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names

    def test_list_dir_recursive(self, core, temp_dir):
        """Test recursive directory listing."""
        (temp_dir / "file1.txt").write_text("content1")
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").write_text("content2")

        from filesystem_mcp.models import ListDirRequest

        request = ListDirRequest(path=".", recursive=True)
        response = core.list_dir(request)

        assert response.total == 3  # file1.txt, subdir, subdir/file2.txt

    def test_list_dir_glob_filter(self, core, temp_dir):
        """Test directory listing with glob filter."""
        (temp_dir / "test.py").write_text("print('hello')")
        (temp_dir / "test.txt").write_text("text")
        (temp_dir / "other.md").write_text("markdown")

        from filesystem_mcp.models import ListDirRequest

        request = ListDirRequest(path=".", glob_pattern="test.*")
        response = core.list_dir(request)

        assert response.total == 2
        names = [e.name for e in response.entries]
        assert "test.py" in names
        assert "test.txt" in names

    def test_list_dir_not_found(self, core):
        """Test listing non-existent directory."""
        from filesystem_mcp.models import ListDirRequest

        request = ListDirRequest(path="nonexistent")
        with pytest.raises(FilesystemError) as exc:
            core.list_dir(request)
        assert exc.value.code == "NOT_FOUND"

    def test_list_dir_not_a_dir(self, core, temp_dir):
        """Test listing a file as directory."""
        (temp_dir / "file.txt").write_text("content")

        from filesystem_mcp.models import ListDirRequest

        request = ListDirRequest(path="file.txt")
        with pytest.raises(FilesystemError) as exc:
            core.list_dir(request)
        assert exc.value.code == "NOT_A_DIR"

    def test_glob_success(self, core, temp_dir):
        """Test glob pattern matching."""
        (temp_dir / "test.py").write_text("print('hello')")
        (temp_dir / "test.txt").write_text("text")
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "test.py").write_text("print('world')")

        from filesystem_mcp.models import GlobRequest

        request = GlobRequest(pattern="**/*.py", path=".")
        response = core.glob(request)

        assert response.total == 2
        assert "test.py" in response.matches
        # On Windows, path separator is backslash
        assert any("subdir" in m and "test.py" in m for m in response.matches)

    def test_glob_not_found(self, core):
        """Test glob on non-existent directory."""
        from filesystem_mcp.models import GlobRequest

        request = GlobRequest(pattern="*.py", path="nonexistent")
        with pytest.raises(FilesystemError) as exc:
            core.glob(request)
        assert exc.value.code == "NOT_FOUND"

    def test_patch_file_success(self, core, temp_dir):
        """Test patching a file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello World")

        from filesystem_mcp.models import PatchFileRequest

        request = PatchFileRequest(path="test.txt", old_str="World", new_str="Universe")
        response = core.patch_file(request)

        assert response.replacements == 1
        assert response.new_size == 14
        assert test_file.read_text() == "Hello Universe"

    def test_patch_file_multiple_replacements(self, core, temp_dir):
        """Test patching with multiple occurrences."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello World World")

        from filesystem_mcp.models import PatchFileRequest

        request = PatchFileRequest(path="test.txt", old_str="World", new_str="Universe")
        response = core.patch_file(request)

        assert response.replacements == 2
        assert test_file.read_text() == "Hello Universe Universe"

    def test_patch_file_not_found(self, core):
        """Test patching non-existent file."""
        from filesystem_mcp.models import PatchFileRequest

        request = PatchFileRequest(path="nonexistent.txt", old_str="old", new_str="new")
        with pytest.raises(FilesystemError) as exc:
            core.patch_file(request)
        assert exc.value.code == "NOT_FOUND"

    def test_patch_file_old_str_not_found(self, core, temp_dir):
        """Test patching with old_str not in file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello World")

        from filesystem_mcp.models import PatchFileRequest

        request = PatchFileRequest(path="test.txt", old_str="Mars", new_str="Venus")
        with pytest.raises(FilesystemError) as exc:
            core.patch_file(request)
        assert exc.value.code == "PATCH_FAILED"

    def test_patch_file_empty_old_str(self, core, temp_dir):
        """Test patching with empty old_str."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello")

        from filesystem_mcp.models import PatchFileRequest

        request = PatchFileRequest(path="test.txt", old_str="", new_str="X")
        with pytest.raises(FilesystemError) as exc:
            core.patch_file(request)
        assert exc.value.code == "PATCH_FAILED"

    def test_patch_file_size_limit(self, _core, temp_dir):
            """Test patch size limit."""
            test_file = temp_dir / "test.txt"
            test_file.write_text("x" * 500)

            from filesystem_mcp.models import PatchFileRequest

            # Config has 1MB limit, but let's test with a config that has small limit
            small_config = FilesystemConfig(root_path=temp_dir, max_file_size=1024)
            small_core = FilesystemCore(small_config)

            request = PatchFileRequest(
            path="test.txt", old_str="x", new_str="xx" * 600
        )  # Would exceed 1024
            with pytest.raises(FileSizeError):
                small_core.patch_file(request)


class TestFilesystemCoreBinaryFiles:
    """Tests for binary file handling."""

    def test_read_binary_file(self, core, temp_dir):
        """Test reading a binary file returns base64."""
        test_file = temp_dir / "binary.dat"
        test_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

        from filesystem_mcp.models import ReadFileRequest

        request = ReadFileRequest(path="binary.dat")
        response = core.read_file(request)

        assert response.is_binary is True
        import base64
        assert base64.b64decode(response.content) == b"\x00\x01\x02\x03\xff\xfe\xfd"

    def test_is_binary_detection(self, core):
        """Test binary detection heuristic."""
        # Null byte = binary
        assert core._is_binary(b"hello\x00world") is True
        # High non-printable ratio = binary
        assert core._is_binary(bytes(range(256))) is True
        # Normal text = not binary
        assert core._is_binary(b"Hello World") is False


class TestFilesystemCoreSymlinks:
    """Tests for symlink handling."""

    def test_symlink_blocked_when_disabled(self, core, temp_dir):
        """Test symlinks are blocked when follow_symlinks=False."""
        # Skip on Windows if no symlink permission
        import platform
        if platform.system() == "Windows":
            pytest.skip("Symlinks may require admin on Windows")

        target = temp_dir / "target.txt"
        target.write_text("target")
        link = temp_dir / "link.txt"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("Cannot create symlinks")

        from filesystem_mcp.models import ReadFileRequest

        request = ReadFileRequest(path="link.txt")
        with pytest.raises(SecurityError) as exc:
            core.read_file(request)
        assert exc.value.code == "SECURITY_ERROR"

    def test_symlink_allowed_when_enabled(self, temp_dir):
        """Test symlinks work when follow_symlinks=True."""
        import platform
        if platform.system() == "Windows":
            pytest.skip("Symlinks may require admin on Windows")

        config = FilesystemConfig(root_path=temp_dir, follow_symlinks=True)
        core = FilesystemCore(config)

        target = temp_dir / "target.txt"
        target.write_text("target content")
        link = temp_dir / "link.txt"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("Cannot create symlinks")

        from filesystem_mcp.models import ReadFileRequest

        request = ReadFileRequest(path="link.txt")
        response = core.read_file(request)

        assert response.content == "target content"


class TestSecurityErrors:
    """Test security-related errors."""

    def test_path_traversal_blocked(self, core, temp_dir):
        """Test path traversal attempts are blocked."""
        from filesystem_mcp.models import ReadFileRequest

        # Create a subdirectory
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "secret.txt").write_text("secret")

        # Try to escape
        request = ReadFileRequest(path="../subdir/secret.txt")
        with pytest.raises(SecurityError):
            core.read_file(request)

    def test_absolute_path_blocked(self, core):
            """Test absolute paths blocked by default."""
            # Use an absolute path - it will be blocked because allow_absolute_paths=False
            import tempfile

            from filesystem_mcp.models import ReadFileRequest

            outside_path = Path(tempfile.gettempdir()) / "outside_test.txt"
            request = ReadFileRequest(path=str(outside_path))
            with pytest.raises(SecurityError) as exc:
                core.read_file(request)
            assert "Absolute paths are not allowed" in exc.value.message


    if __name__ == "__main__":
        pytest.main([__file__, "-v"])
