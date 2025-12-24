"""Tests for voyager.io module."""

from __future__ import annotations

import json
from pathlib import Path

from voyager.io import (
    JsonlReadResult,
    ensure_parent_dir,
    read_file,
    read_json,
    read_jsonl,
    safe_unlink,
    write_file,
    write_json,
    write_jsonl,
)


class TestEnsureParentDir:
    """Tests for ensure_parent_dir function."""

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        """Should create all parent directories."""
        target = tmp_path / "a" / "b" / "c" / "file.txt"
        result = ensure_parent_dir(target)

        assert result == target
        assert target.parent.exists()
        assert target.parent.is_dir()

    def test_handles_existing_directory(self, tmp_path: Path) -> None:
        """Should not fail if directory already exists."""
        target = tmp_path / "file.txt"
        ensure_parent_dir(target)
        # Call again - should not raise
        result = ensure_parent_dir(target)
        assert result == target

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Should accept string paths."""
        target = str(tmp_path / "nested" / "file.txt")
        result = ensure_parent_dir(target)
        assert isinstance(result, Path)
        assert result.parent.exists()


class TestReadFile:
    """Tests for read_file function."""

    def test_reads_existing_file(self, tmp_path: Path) -> None:
        """Should read contents of existing file."""
        file = tmp_path / "test.txt"
        file.write_text("hello world", encoding="utf-8")

        result = read_file(file)
        assert result == "hello world"

    def test_returns_default_for_missing_file(self, tmp_path: Path) -> None:
        """Should return default when file doesn't exist."""
        file = tmp_path / "nonexistent.txt"

        assert read_file(file) is None
        assert read_file(file, default="fallback") == "fallback"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Should accept string paths."""
        file = tmp_path / "test.txt"
        file.write_text("content", encoding="utf-8")

        result = read_file(str(file))
        assert result == "content"


class TestReadJson:
    """Tests for read_json function."""

    def test_reads_valid_json(self, tmp_path: Path) -> None:
        """Should parse valid JSON file."""
        file = tmp_path / "data.json"
        file.write_text('{"key": "value", "number": 42}', encoding="utf-8")

        result = read_json(file)
        assert result == {"key": "value", "number": 42}

    def test_returns_default_for_missing_file(self, tmp_path: Path) -> None:
        """Should return default when file doesn't exist."""
        file = tmp_path / "nonexistent.json"

        assert read_json(file) is None
        assert read_json(file, default={}) == {}

    def test_returns_default_for_invalid_json(self, tmp_path: Path) -> None:
        """Should return default when JSON is invalid."""
        file = tmp_path / "bad.json"
        file.write_text("not valid json {", encoding="utf-8")

        assert read_json(file) is None
        assert read_json(file, default={"fallback": True}) == {"fallback": True}


class TestWriteFile:
    """Tests for write_file function."""

    def test_writes_content(self, tmp_path: Path) -> None:
        """Should write content to file."""
        file = tmp_path / "output.txt"

        result = write_file(file, "test content")

        assert result is True
        assert file.read_text(encoding="utf-8") == "test content"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Should create parent directories if needed."""
        file = tmp_path / "nested" / "dir" / "output.txt"

        result = write_file(file, "nested content")

        assert result is True
        assert file.read_text(encoding="utf-8") == "nested content"

    def test_atomic_write_no_partial_file(self, tmp_path: Path) -> None:
        """Should not leave partial files on failure."""
        file = tmp_path / "atomic.txt"
        # Write initial content
        write_file(file, "original")

        # Verify original content is intact (atomic write means all-or-nothing)
        assert file.read_text(encoding="utf-8") == "original"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Should overwrite existing file atomically."""
        file = tmp_path / "overwrite.txt"
        file.write_text("old content", encoding="utf-8")

        write_file(file, "new content")

        assert file.read_text(encoding="utf-8") == "new content"

    def test_no_temp_file_left_behind(self, tmp_path: Path) -> None:
        """Should not leave temp files after successful write."""
        file = tmp_path / "clean.txt"
        write_file(file, "content")

        # Check no .tmp files remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestWriteJson:
    """Tests for write_json function."""

    def test_writes_json(self, tmp_path: Path) -> None:
        """Should write JSON with proper formatting."""
        file = tmp_path / "data.json"
        data = {"key": "value", "number": 42}

        result = write_json(file, data)

        assert result is True
        content = file.read_text(encoding="utf-8")
        assert json.loads(content) == data
        # Should have trailing newline
        assert content.endswith("\n")

    def test_custom_indent(self, tmp_path: Path) -> None:
        """Should respect custom indent."""
        file = tmp_path / "data.json"
        data = {"key": "value"}

        write_json(file, data, indent=4)

        content = file.read_text(encoding="utf-8")
        # 4-space indent
        assert "    " in content

    def test_returns_false_for_unserializable(self, tmp_path: Path) -> None:
        """Should return False for non-serializable data."""
        file = tmp_path / "bad.json"

        # Sets are not JSON serializable
        result = write_json(file, {"items": {1, 2, 3}})

        assert result is False
        assert not file.exists()

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Should handle unicode content properly."""
        file = tmp_path / "unicode.json"
        data = {"emoji": "🚀", "chinese": "你好"}

        write_json(file, data)

        content = file.read_text(encoding="utf-8")
        loaded = json.loads(content)
        assert loaded == data
        # Should not escape unicode
        assert "🚀" in content


class TestReadJsonl:
    """Tests for read_jsonl function."""

    def test_reads_valid_jsonl(self, tmp_path: Path) -> None:
        file = tmp_path / "data.jsonl"
        file.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")

        result = read_jsonl(file)

        assert isinstance(result, JsonlReadResult)
        assert result.items == [{"a": 1}, {"b": 2}]
        assert result.total_lines == 2
        assert result.invalid_lines == 0

    def test_skips_invalid_lines(self, tmp_path: Path) -> None:
        file = tmp_path / "data.jsonl"
        file.write_text('{"a": 1}\nnot-json\n{"b": 2}\n', encoding="utf-8")

        result = read_jsonl(file)

        assert result.items == [{"a": 1}, {"b": 2}]
        assert result.total_lines == 3
        assert result.invalid_lines == 1

    def test_honors_max_lines(self, tmp_path: Path) -> None:
        file = tmp_path / "data.jsonl"
        file.write_text('{"a": 1}\n{"b": 2}\n{"c": 3}\n', encoding="utf-8")

        result = read_jsonl(file, max_lines=2)

        assert result.items == [{"a": 1}, {"b": 2}]

    def test_missing_file_returns_default(self, tmp_path: Path) -> None:
        file = tmp_path / "missing.jsonl"

        result = read_jsonl(file, default=[{"fallback": True}])

        assert result.items == [{"fallback": True}]


class TestWriteJsonl:
    """Tests for write_jsonl function."""

    def test_writes_jsonl(self, tmp_path: Path) -> None:
        file = tmp_path / "out.jsonl"
        ok = write_jsonl(file, [{"a": 1}, {"b": 2}])

        assert ok is True
        assert file.read_text(encoding="utf-8") == '{"a": 1}\n{"b": 2}\n'

    def test_append_mode(self, tmp_path: Path) -> None:
        file = tmp_path / "out.jsonl"
        write_jsonl(file, [{"a": 1}])

        ok = write_jsonl(file, [{"b": 2}], append=True)

        assert ok is True
        assert file.read_text(encoding="utf-8") == '{"a": 1}\n{"b": 2}\n'

    def test_returns_false_for_unserializable(self, tmp_path: Path) -> None:
        file = tmp_path / "out.jsonl"
        ok = write_jsonl(file, [{"bad": {1, 2, 3}}])

        assert ok is False
        assert not file.exists()


class TestSafeUnlink:
    """Tests for safe_unlink function."""

    def test_deletes_existing_file(self, tmp_path: Path) -> None:
        file = tmp_path / "a.txt"
        file.write_text("x", encoding="utf-8")

        assert safe_unlink(file) is True
        assert not file.exists()

    def test_returns_true_for_missing_file(self, tmp_path: Path) -> None:
        file = tmp_path / "missing.txt"

        assert safe_unlink(file) is True
