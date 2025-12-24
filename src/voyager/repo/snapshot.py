"""Repo snapshot for Session Brain + Curriculum Planner.

Produces a fast, bounded, language-agnostic repo snapshot as a compact JSON
object. Designed to run in < 2s on medium repos and work gracefully when
git is unavailable.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

# Bounds to keep output compact
MAX_TOP_LEVEL_ENTRIES = 50
MAX_RECENT_COMMITS = 10
MAX_HINT_LINES = 20
MAX_HINT_LINE_LENGTH = 200
MAX_HINT_FILE_BYTES = 64_000
HINT_FILES = ("README*", "CONTRIBUTING*", "Makefile", "justfile", "package.json")
HINT_PATTERNS = [
    r"^#+\s*(getting started|quick start|installation|usage|how to|running)",
    r"^(npm|yarn|pnpm|bun)\s+(run|install|start|dev|build|test)",
    r"^(python|pip|uv|rye|poetry)\s+",
    r"^(make|just)\s+\w+",
    r"^(cargo|go|gradle|maven)\s+(run|build|test)",
    r"^\$\s+",  # Shell command examples
]

# Directory summary bounds
DIR_SUMMARY_MAX_DEPTH = 4
DIR_SUMMARY_MAX_ITEMS = 1000

# Optional "tree" view bounds (fd + tree)
FD_MAX_RESULTS = 5000
FD_TREE_MAX_RESULTS = 2000
TREE_MAX_DEPTH = 4
TREE_MAX_LINES = 120
TREE_MAX_CHARS = 8000


def _find_fd_binary() -> str | None:
    return shutil.which("fd") or shutil.which("fdfind")


def _find_tree_binary() -> str | None:
    return shutil.which("tree")


def _run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: float,
    input_text: str | None = None,
) -> str | None:
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _fd_list(
    root: Path,
    *,
    include_hidden: bool,
    max_depth: int | None,
    max_results: int,
    types: list[str],
) -> list[str] | None:
    fd = _find_fd_binary()
    if fd is None:
        return None

    cmd = [
        fd,
        "--strip-cwd-prefix",
        "--exclude",
        ".git",
        "--no-require-git",
        "--max-results",
        str(max_results),
    ]
    if include_hidden:
        cmd.append("--hidden")
    if max_depth is not None:
        cmd.extend(["--max-depth", str(max_depth)])
    for t in types:
        cmd.extend(["--type", t])

    # Match everything.
    cmd.append(".")

    out = _run_cmd(cmd, cwd=root, timeout=1.0)
    if out is None:
        return None

    items = [line.strip() for line in out.splitlines() if line.strip()]
    # fd prints directories with trailing '/', normalize.
    return [item[:-1] if item.endswith("/") else item for item in items]


def _build_tree_from_file_list(root: Path, files: list[str]) -> str | None:
    tree = _find_tree_binary()
    if tree is None:
        return None

    stdin = "\n".join(files) + ("\n" if files else "")
    out = _run_cmd(
        [
            tree,
            "--fromfile",
            "--noreport",
            "--charset",
            "ascii",
            "-L",
            str(TREE_MAX_DEPTH),
        ],
        cwd=root,
        timeout=1.0,
        input_text=stdin,
    )
    if out is None:
        return None

    # Bound output.
    lines: list[str] = []
    total_chars = 0
    for line in out.splitlines():
        if len(lines) >= TREE_MAX_LINES:
            break
        if total_chars + len(line) + 1 > TREE_MAX_CHARS:
            break
        lines.append(line.rstrip())
        total_chars += len(line) + 1
    return "\n".join(lines).strip() if lines else None


def _directory_summary_from_files(files: list[str]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for rel in files:
        parts = rel.split("/", 1)
        if len(parts) < 2:
            continue  # file at root, not part of a top-level dir summary
        top = parts[0]
        if top.startswith("."):
            continue
        summary[top] = min(summary.get(top, 0) + 1, DIR_SUMMARY_MAX_ITEMS)
    return summary


@dataclass(frozen=True)
class _IgnoreRule:
    pattern: str
    negate: bool
    dir_only: bool
    anchored: bool


class _Gitignore:
    """Small, best-effort gitignore matcher.

    This is intentionally incomplete; it targets the common patterns used to
    exclude large build/vendor directories for fast repo snapshots.
    """

    def __init__(self, rules: list[_IgnoreRule]) -> None:
        self._rules = rules

    @classmethod
    def from_root(cls, root: Path) -> _Gitignore:
        rules: list[_IgnoreRule] = []
        path = root / ".gitignore"
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            negate = line.startswith("!")
            if negate:
                line = line[1:].strip()
            if not line:
                continue

            anchored = line.startswith("/")
            if anchored:
                line = line[1:]

            dir_only = line.endswith("/")
            if dir_only:
                line = line[:-1]

            if line:
                rules.append(
                    _IgnoreRule(
                        pattern=line,
                        negate=negate,
                        dir_only=dir_only,
                        anchored=anchored,
                    )
                )

        return cls(rules)

    def is_ignored(self, rel_path: Path, *, is_dir: bool) -> bool:
        """Return True if rel_path should be ignored."""
        rel_posix = rel_path.as_posix().lstrip("./")
        parts = rel_path.parts

        ignored = False
        for rule in self._rules:
            if rule.dir_only and not is_dir:
                continue

            pattern = rule.pattern

            matched = False
            if rule.anchored:
                matched = fnmatchcase(rel_posix, pattern)
            else:
                if "/" in pattern:
                    matched = fnmatchcase(rel_posix, pattern)
                else:
                    matched = any(fnmatchcase(part, pattern) for part in parts)

            if matched:
                ignored = not rule.negate

        return ignored


@dataclass
class RepoSnapshot:
    """Snapshot of repository state."""

    root: str
    git_available: bool = False
    branch: str | None = None
    status: list[str] = field(default_factory=list)
    recent_commits: list[dict[str, str]] = field(default_factory=list)
    top_level: list[dict[str, str]] = field(default_factory=list)
    directory_summary: dict[str, int] = field(default_factory=dict)
    file_tree: str | None = None
    run_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {"root": self.root}

        if self.git_available:
            result["git"] = {
                "branch": self.branch,
                "status": self.status,
                "recent_commits": self.recent_commits,
            }

        result["files"] = {
            "top_level": self.top_level,
            "directory_summary": self.directory_summary,
        }
        if self.file_tree:
            result["files"]["tree"] = self.file_tree

        if self.run_hints:
            result["run_hints"] = self.run_hints

        return result


def _run_git(args: list[str], cwd: Path, timeout: float = 5.0) -> str | None:
    """Run a git command, returning stdout or None on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


GitInfo = tuple[bool, str | None, list[str], list[dict[str, str]]]


def _get_git_info(root: Path) -> GitInfo:
    """Get git branch, status, and recent commits.

    Returns:
        Tuple of (git_available, branch, status_lines, commits)
    """
    # Check if git is available and this is a repo
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    if branch is None:
        return False, None, [], []

    # Get status (porcelain for stable parsing)
    status_output = _run_git(["status", "--porcelain", "-uno"], root) or ""
    status_lines = [line for line in status_output.split("\n") if line.strip()]

    # Get recent commits (short format)
    log_output = (
        _run_git(
            ["log", f"-{MAX_RECENT_COMMITS}", "--oneline", "--no-decorate"],
            root,
        )
        or ""
    )
    commits = []
    for line in log_output.split("\n"):
        if line.strip():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                commits.append({"sha": parts[0], "message": parts[1]})
            elif parts:
                commits.append({"sha": parts[0], "message": ""})

    return True, branch, status_lines, commits


def _get_top_level_entries(root: Path) -> list[dict[str, str]]:
    """Get top-level directory entries with types."""
    fd_items = _fd_list(
        root,
        include_hidden=False,
        max_depth=1,
        max_results=MAX_TOP_LEVEL_ENTRIES * 5,
        types=["f", "d"],
    )
    if fd_items is not None:
        entries: list[dict[str, str]] = []
        for item in fd_items:
            name = Path(item).name
            if name.startswith("."):
                continue
            full = root / item
            entry_type = "dir" if full.is_dir(follow_symlinks=False) else "file"
            entries.append({"name": name, "type": entry_type})
            if len(entries) >= MAX_TOP_LEVEL_ENTRIES:
                break
        return entries

    ignore = _Gitignore.from_root(root)
    entries = []
    try:
        for item in sorted(root.iterdir()):
            if item.name.startswith("."):
                continue  # Skip hidden files
            item_is_dir = item.is_dir(follow_symlinks=False)
            rel = item.relative_to(root)
            if ignore.is_ignored(rel, is_dir=item_is_dir):
                continue
            entry_type = "dir" if item_is_dir else "file"
            entries.append({"name": item.name, "type": entry_type})
            if len(entries) >= MAX_TOP_LEVEL_ENTRIES:
                break
    except OSError:
        pass
    return entries


def _get_directory_summary(root: Path) -> dict[str, int]:
    """Get a summary of directory structure (count of items per top-level dir)."""
    fd_files = _fd_list(
        root,
        include_hidden=True,
        max_depth=None,
        max_results=FD_MAX_RESULTS,
        types=["f"],
    )
    if fd_files is not None:
        return _directory_summary_from_files(fd_files)

    ignore = _Gitignore.from_root(root)
    summary: dict[str, int] = {}

    def count_dir(top_dir: Path) -> int:
        count = 0
        queue: list[tuple[Path, int]] = [(top_dir, 0)]

        while queue and count < DIR_SUMMARY_MAX_ITEMS:
            current, depth = queue.pop()
            if depth > DIR_SUMMARY_MAX_DEPTH:
                continue
            try:
                for entry in current.iterdir():
                    if entry.name.startswith("."):
                        continue
                    entry_is_dir = entry.is_dir(follow_symlinks=False)
                    rel = entry.relative_to(root)
                    if ignore.is_ignored(rel, is_dir=entry_is_dir):
                        continue

                    count += 1
                    if count >= DIR_SUMMARY_MAX_ITEMS:
                        return DIR_SUMMARY_MAX_ITEMS
                    if entry_is_dir and depth < DIR_SUMMARY_MAX_DEPTH:
                        queue.append((entry, depth + 1))
            except OSError:
                continue

        return min(count, DIR_SUMMARY_MAX_ITEMS)

    try:
        for item in root.iterdir():
            if item.name.startswith("."):
                continue
            if item.is_dir(follow_symlinks=False):
                rel = item.relative_to(root)
                if ignore.is_ignored(rel, is_dir=True):
                    continue
                try:
                    summary[item.name] = count_dir(item)
                except OSError:
                    summary[item.name] = 0
    except OSError:
        pass
    return summary


def _extract_run_hints(root: Path) -> list[str]:
    """Extract how-to-run hints from common documentation files."""
    ignore = _Gitignore.from_root(root)
    hints: list[str] = []
    hint_patterns = [re.compile(p, re.IGNORECASE) for p in HINT_PATTERNS]

    for pattern in HINT_FILES:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue
            if ignore.is_ignored(rel, is_dir=False):
                continue
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(MAX_HINT_FILE_BYTES)
                for line in content.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # Check if line matches any hint pattern
                    for regex in hint_patterns:
                        if regex.search(line):
                            truncated = line[:MAX_HINT_LINE_LENGTH]
                            if truncated not in hints:
                                hints.append(truncated)
                            break
                    if len(hints) >= MAX_HINT_LINES:
                        break
            except OSError:
                continue
            if len(hints) >= MAX_HINT_LINES:
                break

    return hints


def create_snapshot(root: Path | str | None = None) -> RepoSnapshot:
    """Create a snapshot of the repository.

    Args:
        root: Repository root path. Defaults to current directory.

    Returns:
        RepoSnapshot with git info, file listing, and run hints.
    """
    root = Path.cwd() if root is None else Path(root).resolve()

    # Try to find git root
    git_root = _run_git(["rev-parse", "--show-toplevel"], root)
    if git_root:
        root = Path(git_root)

    snapshot = RepoSnapshot(root=str(root))

    # Collect git info
    git_available, branch, status, commits = _get_git_info(root)
    snapshot.git_available = git_available
    snapshot.branch = branch
    snapshot.status = status
    snapshot.recent_commits = commits

    # Collect file info
    snapshot.top_level = _get_top_level_entries(root)
    snapshot.directory_summary = _get_directory_summary(root)

    # Optional tree view (fd + tree)
    fd_files_for_tree = _fd_list(
        root,
        include_hidden=True,
        max_depth=None,
        max_results=FD_TREE_MAX_RESULTS,
        types=["f"],
    )
    if fd_files_for_tree is not None:
        snapshot.file_tree = _build_tree_from_file_list(root, fd_files_for_tree)

    # Extract run hints
    snapshot.run_hints = _extract_run_hints(root)

    return snapshot


def snapshot_to_json(root: Path | str | None = None) -> dict[str, Any]:
    """Create a snapshot and return as JSON-serializable dict.

    Args:
        root: Repository root path. Defaults to current directory.

    Returns:
        Dictionary representation of the snapshot.
    """
    return create_snapshot(root).to_dict()
