"""Tests for FilesystemConfig model."""

import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from filesystem_mcp.models import FilesystemConfig


class TestFilesystemConfig:
    """Tests for FilesystemConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = FilesystemConfig()
        assert config.root_path == Path.cwd()
        assert config.max_file_size == 10 * 1024 * 1024
        assert config.follow_symlinks is False
        assert config.allow_absolute_paths is False
        assert config.default_encoding == "utf-8"

    def test_custom_root_path(self):
        """Test custom root path configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = FilesystemConfig(root_path=tmpdir)
            assert config.root_path == Path(tmpdir).resolve()

    def test_root_path_expands_user(self):
        """Test that root path expands ~."""
        config = FilesystemConfig(root_path="~/test")
        assert str(config.root_path).startswith(str(Path.home()))

    def test_max_file_size_bounds(self):
        """Test max_file_size validation bounds."""
        # Valid sizes
        config = FilesystemConfig(max_file_size=1024)
        assert config.max_file_size == 1024

        config = FilesystemConfig(max_file_size=1024 * 1024 * 1024)
        assert config.max_file_size == 1024 * 1024 * 1024

        # Too small
        with pytest.raises(ValidationError):
            FilesystemConfig(max_file_size=512)

        # Too large
        with pytest.raises(ValidationError):
            FilesystemConfig(max_file_size=1024 * 1024 * 1024 * 2)

    def test_env_override(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv("FILE_BRIDGE_ROOT_PATH", "/custom/root")
        monkeypatch.setenv("FILE_BRIDGE_MAX_FILE_SIZE", "2048")
        monkeypatch.setenv("FILE_BRIDGE_FOLLOW_SYMLINKS", "true")
        monkeypatch.setenv("FILE_BRIDGE_ALLOW_ABSOLUTE_PATHS", "true")
        monkeypatch.setenv("FILE_BRIDGE_DEFAULT_ENCODING", "latin-1")

        config = FilesystemConfig()
        assert config.root_path == Path("/custom/root").resolve()
        assert config.max_file_size == 2048
        assert config.follow_symlinks is True
        assert config.allow_absolute_paths is True
        assert config.default_encoding == "latin-1"

    def test_legacy_env_prefix(self, monkeypatch):
        """Legacy FILESYSTEM_MCP_* still works when FILE_BRIDGE_* unset."""
        for key in list(__import__("os").environ):
            if key.startswith(("FILE_BRIDGE_", "FILESYSTEM_MCP_")):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("FILESYSTEM_MCP_ROOT_PATH", "/legacy/root")
        monkeypatch.setenv("FILESYSTEM_MCP_MAX_FILE_SIZE", "4096")

        config = FilesystemConfig()
        assert config.root_path == Path("/legacy/root").resolve()
        assert config.max_file_size == 4096

    def test_canonical_env_wins_over_legacy(self, monkeypatch):
        """FILE_BRIDGE_* takes precedence over FILESYSTEM_MCP_*."""
        monkeypatch.setenv("FILESYSTEM_MCP_ROOT_PATH", "/legacy/root")
        monkeypatch.setenv("FILE_BRIDGE_ROOT_PATH", "/canonical/root")

        config = FilesystemConfig()
        assert config.root_path == Path("/canonical/root").resolve()
