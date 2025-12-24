"""Safe I/O helpers for Voyager.

Provides atomic writes and graceful file reading to keep hook scripts
robust and deterministic. All operations are designed to never crash
hooks - missing files return defaults, writes are atomic.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def ensure_parent_dir(path: Path | str) -> Path:
    """Ensure the parent directory of a path exists.

    Args:
        path: File path whose parent directory should be created.

    Returns:
        The path as a Path object.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_file(path: Path | str, default: str | None = None) -> str | None:
    """Read a file's contents, returning default if missing or unreadable.

    Args:
        path: Path to the file to read.
        default: Value to return if file doesn't exist or can't be read.

    Returns:
        File contents as string, or default if file is missing/unreadable.
    """
    try:
        return Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, OSError):
        return default


def read_json(path: Path | str, default: Any = None) -> Any:
    """Read and parse a JSON file, returning default on any error.

    Args:
        path: Path to the JSON file.
        default: Value to return if file is missing or JSON is invalid.

    Returns:
        Parsed JSON data, or default on any error.
    """
    content = read_file(path)
    if content is None:
        return default
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return default


def write_file(path: Path | str, content: str) -> bool:
    """Write content to a file atomically.

    Uses write-to-temp + rename pattern to ensure the file is never
    left in a partial/corrupt state.

    Args:
        path: Destination file path.
        content: String content to write.

    Returns:
        True if write succeeded, False otherwise.
    """
    path = Path(path)
    try:
        ensure_parent_dir(path)
        # Create temp file in same directory for atomic rename
        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=path.name + ".",
            dir=path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            # Atomic replace (works even if destination exists)
            os.replace(tmp_path, path)
            return True
        except Exception:
            # Clean up temp file on failure
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
    except (OSError, PermissionError):
        return False


def write_json(
    path: Path | str,
    data: Any,
    indent: int = 2,
) -> bool:
    """Write data as JSON to a file atomically.

    Args:
        path: Destination file path.
        data: Data to serialize as JSON.
        indent: JSON indentation level (default 2).

    Returns:
        True if write succeeded, False otherwise.
    """
    try:
        content = json.dumps(data, indent=indent, ensure_ascii=False)
        # Add trailing newline for POSIX compliance
        if not content.endswith("\n"):
            content += "\n"
        return write_file(path, content)
    except (TypeError, ValueError):
        # JSON serialization failed
        return False


@dataclasses.dataclass(frozen=True)
class JsonlReadResult:
    """Result of reading a JSONL file."""

    items: list[Any]
    total_lines: int
    invalid_lines: int


def read_jsonl(
    path: Path | str,
    *,
    max_lines: int | None = None,
    default: list[Any] | None = None,
) -> JsonlReadResult:
    """Read and parse a JSON Lines (JSONL) file.

    Never raises. Invalid JSON lines are skipped and counted.

    Args:
        path: Path to the JSONL file.
        max_lines: Optional maximum number of *valid* items to return.
        default: Default items to return if file is missing/unreadable.

    Returns:
        JsonlReadResult with parsed items and basic stats.
    """
    path = Path(path)

    items: list[Any] = []
    total_lines = 0
    invalid_lines = 0

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                total_lines += 1
                if not line.strip():
                    continue
                try:
                    items.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    invalid_lines += 1
                    continue
                if max_lines is not None and len(items) >= max_lines:
                    break
    except (FileNotFoundError, PermissionError, OSError):
        return JsonlReadResult(items=default or [], total_lines=0, invalid_lines=0)

    return JsonlReadResult(
        items=items,
        total_lines=total_lines,
        invalid_lines=invalid_lines,
    )


def write_jsonl(
    path: Path | str,
    items: Iterable[Any],
    *,
    append: bool = False,
) -> bool:
    """Write items to a JSONL file.

    Args:
        path: Destination file path.
        items: Iterable of JSON-serializable items.
        append: If True, append to the file (not atomic). If False, replace
            the file atomically.

    Returns:
        True if write succeeded, False otherwise.
    """
    path = Path(path)
    try:
        ensure_parent_dir(path)
    except (OSError, PermissionError):
        return False

    mode = "a" if append else "w"

    try:
        with path.open(mode, encoding="utf-8") as f:
            for item in items:
                try:
                    line = json.dumps(item, ensure_ascii=False)
                    f.write(line + "\n")
                except (TypeError, ValueError):
                    # Clean up partial file on error (only for non-append mode)
                    if not append:
                        safe_unlink(path)
                    return False
        return True
    except (OSError, PermissionError):
        return False


def safe_unlink(path: Path | str) -> bool:
    """Delete a file if it exists.

    Returns True if the file was removed or did not exist, False on failure.
    """
    try:
        Path(path).unlink(missing_ok=True)
        return True
    except (OSError, PermissionError, ValueError):
        return False
