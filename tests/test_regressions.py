"""Regression tests for the 2026-10 safety and reliability review."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from filesystem_mcp.core import (
    ConfigError,
    FileSizeError,
    FilesystemCore,
    FilesystemError,
    SecurityError,
)
from filesystem_mcp.models import (
    FilesystemConfig,
    GlobRequest,
    ListDirRequest,
    PatchFileRequest,
    ReadFileRequest,
    SearchFilesRequest,
    WriteFileRequest,
)

needs_rg = pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")
windows_only = pytest.mark.skipif(os.name != "nt", reason="NTFS junctions are Windows-only")


@pytest.fixture
def base():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def root(base):
    r = base / "matters"
    r.mkdir()
    return r


@pytest.fixture
def outside(base):
    o = base / "OTHER_CLIENT"
    o.mkdir()
    (o / "secret-settlement.txt").write_text("settlement 250000", encoding="utf-8")
    return o


def make_core(root: Path, **kwargs: object) -> FilesystemCore:
    return FilesystemCore(FilesystemConfig(root_path=root, **kwargs))


def junction(link: Path, target: Path) -> None:
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],  # noqa: S607
        check=True,
        capture_output=True,
    )


class TestStartupSafety:
    def test_missing_root_refused(self, monkeypatch):
        for key in list(os.environ):
            if key.startswith(("FILE_BRIDGE_", "FILESYSTEM_MCP_")):
                monkeypatch.delenv(key, raising=False)
        with pytest.raises(ConfigError):
            FilesystemCore(FilesystemConfig())

    def test_drive_root_refused(self):
        anchor = Path(Path.cwd().anchor)
        with pytest.raises(ConfigError):
            make_core(anchor)

    def test_home_refused_unless_allowed(self):
        with pytest.raises(ConfigError):
            make_core(Path.home())
        assert make_core(Path.home(), allow_broad_root=True).root == Path.home().resolve()

    def test_missing_folder_refused(self, base):
        with pytest.raises(ConfigError):
            make_core(base / "does-not-exist")


class TestFolderFence:
    @windows_only
    def test_junction_to_outside_is_not_listed(self, root, outside):
        junction(root / "link-out", outside)
        core = make_core(root)
        listed = [e.path for e in core.list_dir(ListDirRequest(path=".", recursive=True)).entries]
        assert not any("secret" in p or "link-out" in p for p in listed)
        globbed = core.glob(GlobRequest(pattern="**/*.txt")).matches
        assert not any("secret" in p for p in globbed)
        with pytest.raises(SecurityError):
            core.read_file(ReadFileRequest(path="link-out/secret-settlement.txt"))

    @windows_only
    def test_junction_inside_root_listed_but_not_followed(self, root):
        (root / "real").mkdir()
        (root / "real" / "a.txt").write_text("a", encoding="utf-8")
        junction(root / "alias", root / "real")
        core = make_core(root)
        listing = core.list_dir(ListDirRequest(path=".", recursive=True))
        entries = {e.path: e for e in listing.entries}
        assert entries["alias"].is_symlink is True
        assert not any(p.startswith("alias" + os.sep) for p in entries)

    @windows_only
    def test_broken_junction_does_not_break_listing(self, base, root):
        gone = base / "gone"
        gone.mkdir()
        junction(root / "broken", gone)
        gone.rmdir()
        (root / "ok.txt").write_text("ok", encoding="utf-8")
        core = make_core(root)
        names = [e.name for e in core.list_dir(ListDirRequest(path=".")).entries]
        assert "ok.txt" in names

    def test_glob_rejects_parent_and_absolute_patterns(self, root):
        core = make_core(root)
        for pattern in ["../*", "a/../../*", "/etc/*", "C:/Windows/*"]:
            with pytest.raises(SecurityError):
                core.glob(GlobRequest(pattern=pattern))

    def test_max_depth_counts_levels(self, root):
        (root / "a" / "b" / "c").mkdir(parents=True)
        core = make_core(root)
        one = core.list_dir(ListDirRequest(path=".", recursive=True, max_depth=1)).entries
        assert [e.path for e in one] == ["a"]
        two = core.list_dir(ListDirRequest(path=".", recursive=True, max_depth=2)).entries
        assert sorted(e.path for e in two) == ["a", str(Path("a") / "b")]

    def test_recursive_glob_filter_only_returns_matches(self, root):
        (root / "sub").mkdir()
        (root / "sub" / "x.py").write_text("x", encoding="utf-8")
        core = make_core(root)
        paths = [
            e.path
            for e in core.list_dir(
                ListDirRequest(path=".", recursive=True, glob_pattern="*.py")
            ).entries
        ]
        assert paths == [str(Path("sub") / "x.py")]

    def test_bridge_data_folder_hidden_and_protected(self, root):
        core = make_core(root, read_only=False)
        (root / "doc.txt").write_text("v1", encoding="utf-8")
        core.write_file(WriteFileRequest(path="doc.txt", content="v2"))
        request = ListDirRequest(path=".", recursive=True, include_hidden=True)
        listed = [e.path for e in core.list_dir(request).entries]
        assert listed == ["doc.txt"]
        with pytest.raises(SecurityError):
            core.write_file(WriteFileRequest(path=".file-bridge/versions/x.txt", content="tamper"))


class TestSizeLimit:
    def test_request_cannot_raise_admin_cap(self, root):
        (root / "big.txt").write_text("x" * 5000, encoding="utf-8")
        core = make_core(root, max_file_size=1024)
        with pytest.raises(FileSizeError):
            core.read_file(ReadFileRequest(path="big.txt", max_size=10**9))

    def test_request_can_lower_cap(self, root):
        (root / "mid.txt").write_text("x" * 600, encoding="utf-8")
        core = make_core(root, max_file_size=1024)
        with pytest.raises(FileSizeError):
            core.read_file(ReadFileRequest(path="mid.txt", max_size=500))


class TestEncoding:
    def test_non_latin_utf8_is_text(self, root):
        (root / "greek.txt").write_text("Συμβόλαιο μίσθωσης " * 20, encoding="utf-8")
        result = make_core(root).read_file(ReadFileRequest(path="greek.txt"))
        assert result.is_binary is False
        assert result.content.startswith("Συμβόλαιο")

    def test_legacy_windows_text_is_read(self, root):
        (root / "letter.txt").write_bytes("Fee: £500 agreed".encode("cp1252"))
        result = make_core(root).read_file(ReadFileRequest(path="letter.txt"))
        assert result.is_binary is False
        assert result.content == "Fee: £500 agreed"
        assert result.encoding == "cp1252"

    def test_utf16_with_bom_is_text(self, root):
        (root / "export.txt").write_bytes("Client list".encode("utf-16"))
        result = make_core(root).read_file(ReadFileRequest(path="export.txt"))
        assert result.content == "Client list"

    def test_unknown_encoding_is_a_clear_error(self, root):
        (root / "a.txt").write_text("a", encoding="utf-8")
        with pytest.raises(FilesystemError) as exc:
            make_core(root).read_file(ReadFileRequest(path="a.txt", encoding="not-a-codec"))
        assert exc.value.code == "INVALID_ENCODING"


@needs_rg
class TestSearch:
    def test_terms_starting_with_a_dash_are_found(self, root):
        (root / "a.txt").write_text("discount -5% applies\n--DRAFT-- note\n", encoding="utf-8")
        core = make_core(root)
        assert core.search_files(SearchFilesRequest(pattern="-5%")).total == 1
        assert core.search_files(SearchFilesRequest(pattern="--DRAFT--")).total == 1

    def test_invalid_regex_is_an_error_not_zero_matches(self, root):
        (root / "a.txt").write_text("text", encoding="utf-8")
        with pytest.raises(FilesystemError) as exc:
            make_core(root).search_files(SearchFilesRequest(pattern="(unclosed"))
        assert exc.value.code == "SEARCH_ERROR"

    def test_fixed_strings(self, root):
        (root / "a.txt").write_text("fee (estimate) only", encoding="utf-8")
        result = make_core(root).search_files(
            SearchFilesRequest(pattern="(estimate)", fixed_strings=True)
        )
        assert result.total == 1

    def test_legacy_file_does_not_break_search(self, root):
        (root / "legacy.txt").write_bytes("Fee: £500 agreed".encode("cp1252"))
        (root / "modern.txt").write_text("also agreed", encoding="utf-8")
        result = make_core(root).search_files(SearchFilesRequest(pattern="agreed"))
        assert result.total == 2
        assert any("£500" in m.match for m in result.matches)

    def test_results_are_relative_with_context(self, root):
        (root / "sub").mkdir()
        (root / "sub" / "a.txt").write_text("one\r\ntwo\r\nTARGET\r\nfour\r\n", encoding="utf-8")
        result = make_core(root).search_files(SearchFilesRequest(pattern="TARGET", context_lines=1))
        match = result.matches[0]
        assert match.file == str(Path("sub") / "a.txt")
        assert match.match == "TARGET"
        assert match.line == 3
        assert match.column == 1
        assert match.context_before == ["two"]
        assert match.context_after == ["four"]

    def test_non_ascii_match_text(self, root):
        (root / "a.txt").write_text("Café Müller agreed", encoding="utf-8")
        result = make_core(root).search_files(SearchFilesRequest(pattern="agreed"))
        assert result.matches[0].match == "Café Müller agreed"

    def test_truncated_only_when_more_exist(self, root):
        (root / "a.txt").write_text("hit\nhit\n", encoding="utf-8")
        core = make_core(root)
        two = core.search_files(SearchFilesRequest(pattern="hit", max_results=2))
        one = core.search_files(SearchFilesRequest(pattern="hit", max_results=1))
        assert two.truncated is False
        assert one.truncated is True


class TestWriting:
    def test_read_only_by_default(self, root):
        (root / "a.txt").write_text("a", encoding="utf-8")
        core = make_core(root)
        with pytest.raises(FilesystemError) as exc:
            core.write_file(WriteFileRequest(path="a.txt", content=""))
        assert exc.value.code == "READ_ONLY"
        with pytest.raises(FilesystemError):
            core.patch_file(PatchFileRequest(path="a.txt", old_str="a", new_str="b"))
        assert (root / "a.txt").read_text(encoding="utf-8") == "a"

    def test_write_keeps_previous_version(self, root):
        (root / "a.txt").write_text("first", encoding="utf-8")
        core = make_core(root, read_only=False)
        response = core.write_file(WriteFileRequest(path="a.txt", content="second"))
        assert response.backup is not None
        assert (root / response.backup).read_text(encoding="utf-8") == "first"

    def test_patch_preserves_unix_line_endings(self, root):
        (root / "lf.txt").write_bytes(b"one\ntwo\nthree\n")
        make_core(root, read_only=False).patch_file(
            PatchFileRequest(path="lf.txt", old_str="two", new_str="2")
        )
        assert (root / "lf.txt").read_bytes() == b"one\n2\nthree\n"

    def test_patch_matches_windows_line_endings(self, root):
        (root / "crlf.txt").write_bytes(b"one\r\ntwo\r\nthree\r\n")
        make_core(root, read_only=False).patch_file(
            PatchFileRequest(path="crlf.txt", old_str="one\ntwo", new_str="1\n2")
        )
        assert (root / "crlf.txt").read_bytes() == b"1\r\n2\r\nthree\r\n"

    def test_patch_refuses_ambiguous_match(self, root):
        (root / "c.txt").write_text("Clause A. Clause A.", encoding="utf-8")
        core = make_core(root, read_only=False)
        with pytest.raises(FilesystemError) as exc:
            core.patch_file(PatchFileRequest(path="c.txt", old_str="Clause A", new_str="Clause B"))
        assert exc.value.details["occurrences"] == 2
        assert (root / "c.txt").read_text(encoding="utf-8") == "Clause A. Clause A."

    def test_patch_keeps_legacy_encoding(self, root):
        (root / "l.txt").write_bytes("Fee £500".encode("cp1252"))
        make_core(root, read_only=False).patch_file(
            PatchFileRequest(path="l.txt", old_str="500", new_str="600")
        )
        assert (root / "l.txt").read_bytes() == "Fee £600".encode("cp1252")

    def test_size_checked_before_creating_folders(self, root):
        core = make_core(root, read_only=False, max_file_size=1024)
        with pytest.raises(FileSizeError):
            core.write_file(WriteFileRequest(path="new/dir/a.txt", content="x" * 2000))
        assert not (root / "new").exists()


class TestCommandLine:
    def _run(self, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "filesystem_mcp.server", *args],
            capture_output=True,
            text=True,
            env=env,
            stdin=subprocess.DEVNULL,
            timeout=60,
        )

    def _env(self, **extra: str) -> dict[str, str]:
        prefixes = ("FILE_BRIDGE_", "FILESYSTEM_MCP_")
        env = {k: v for k, v in os.environ.items() if not k.startswith(prefixes)}
        env.update(extra)
        return env

    def test_version_and_help_exit_cleanly(self):
        assert self._run("--version", env=self._env()).returncode == 0
        assert self._run("--help", env=self._env()).returncode == 0

    def test_refuses_to_start_without_folder(self):
        result = self._run(env=self._env())
        assert result.returncode == 2
        assert "FILE_BRIDGE_ROOT_PATH" in result.stderr

    def test_check_reports_mode(self, root):
        result = self._run("--check", env=self._env(FILE_BRIDGE_ROOT_PATH=str(root)))
        assert result.returncode == 0
        assert "read-only" in result.stdout
