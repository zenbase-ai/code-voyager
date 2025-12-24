"""Tests for voyager.repo.snapshot module."""

from __future__ import annotations

from pathlib import Path

from voyager.repo.snapshot import snapshot_to_json


class TestSnapshotGitignore:
    def test_respects_root_gitignore(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text(
            "ignored_dir/\nignored.txt\n",
            encoding="utf-8",
        )

        (tmp_path / "kept_dir").mkdir()
        (tmp_path / "kept_dir" / "a.txt").write_text("ok", encoding="utf-8")

        (tmp_path / "ignored_dir").mkdir()
        (tmp_path / "ignored_dir" / "b.txt").write_text("nope", encoding="utf-8")

        (tmp_path / "keep.txt").write_text("ok", encoding="utf-8")
        (tmp_path / "ignored.txt").write_text("nope", encoding="utf-8")

        snapshot = snapshot_to_json(tmp_path)
        top_level = snapshot["files"]["top_level"]
        names = {e["name"] for e in top_level}

        assert "kept_dir" in names
        assert "keep.txt" in names
        assert "ignored_dir" not in names
        assert "ignored.txt" not in names

        directory_summary = snapshot["files"]["directory_summary"]
        assert "kept_dir" in directory_summary
        assert "ignored_dir" not in directory_summary


class TestSnapshotBounds:
    def test_directory_summary_caps_at_1000(self, tmp_path: Path) -> None:
        (tmp_path / "big").mkdir()
        for i in range(1005):
            (tmp_path / "big" / f"f{i}.txt").write_text("x", encoding="utf-8")

        snapshot = snapshot_to_json(tmp_path)
        directory_summary = snapshot["files"]["directory_summary"]

        assert directory_summary["big"] == 1000
