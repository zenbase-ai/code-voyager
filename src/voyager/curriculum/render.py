"""Curriculum renderer for Voyager.

Renders curriculum.json to human-readable Markdown format.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from voyager.config import get_curriculum_md_path
from voyager.io import write_file
from voyager.logging import get_logger

_logger = get_logger("curriculum.render")

# Status icons for task states
STATUS_ICONS = {
    "pending": " ",
    "in_progress": "~",
    "done": "x",
    "blocked": "!",
}


def render_curriculum_md(curriculum: dict[str, Any]) -> str:
    """Render curriculum dict to Markdown format.

    Args:
        curriculum: Curriculum dict conforming to schema.

    Returns:
        Markdown string representation.
    """
    lines: list[str] = []

    # Header
    goal = curriculum.get("goal", "")
    lines.append("# Curriculum")
    lines.append("")

    if goal:
        lines.append(f"> **Goal:** {goal}")
        lines.append("")

    # Metadata summary
    metadata = curriculum.get("metadata", {})
    total_tasks = metadata.get("total_tasks", 0)
    updated_at = metadata.get("updated_at", "")

    if total_tasks or updated_at:
        meta_parts = []
        if total_tasks:
            meta_parts.append(f"{total_tasks} tasks")
        if updated_at:
            meta_parts.append(f"Updated: {updated_at[:10]}")
        lines.append(f"_{' | '.join(meta_parts)}_")
        lines.append("")

    # Tracks
    tracks = curriculum.get("tracks", [])
    if not tracks:
        lines.append("_No tasks planned yet._")
        return "\n".join(lines)

    for track in tracks:
        track_name = track.get("name", "unnamed")
        track_desc = track.get("description", "")
        tasks = track.get("tasks", [])

        lines.append(f"## {track_name.title()}")
        if track_desc:
            lines.append(f"_{track_desc}_")
        lines.append("")

        if not tasks:
            lines.append("_No tasks in this track._")
            lines.append("")
            continue

        for task in tasks:
            _render_task(task, lines)
            lines.append("")

    return "\n".join(lines)


def _render_task(task: dict[str, Any], lines: list[str]) -> None:
    """Render a single task to markdown lines.

    Args:
        task: Task dict.
        lines: List to append rendered lines to.
    """
    task_id = task.get("id", "?")
    title = task.get("title", "Untitled")
    status = task.get("status", "pending")
    scope = task.get("estimated_scope", "")
    why = task.get("why", "")
    criteria = task.get("acceptance_criteria", [])
    suggested_files = task.get("suggested_files", [])
    commands = task.get("commands_to_run", [])
    depends_on = task.get("depends_on", [])

    # Task header with checkbox
    icon = STATUS_ICONS.get(status, " ")
    scope_badge = f" `[{scope}]`" if scope else ""
    lines.append(f"- [{icon}] **{task_id}**: {title}{scope_badge}")

    # Why (indented)
    if why:
        lines.append(f"  - _Why:_ {why}")

    # Dependencies
    if depends_on:
        deps = ", ".join(depends_on)
        lines.append(f"  - _Depends on:_ {deps}")

    # Acceptance criteria
    if criteria:
        lines.append("  - Acceptance criteria:")
        for crit in criteria:
            lines.append(f"    - {crit}")

    # Files
    if suggested_files:
        files = ", ".join(f"`{f}`" for f in suggested_files[:5])
        lines.append(f"  - Files: {files}")

    # Commands
    if commands:
        cmds = ", ".join(f"`{c}`" for c in commands[:3])
        lines.append(f"  - Verify: {cmds}")


def render_compact(curriculum: dict[str, Any]) -> str:
    """Render a compact one-line summary of the curriculum.

    Args:
        curriculum: Curriculum dict.

    Returns:
        Short summary string.
    """
    goal = curriculum.get("goal", "")[:50]
    tracks = curriculum.get("tracks", [])
    total_tasks = sum(len(t.get("tasks", [])) for t in tracks)

    parts = []
    if goal:
        parts.append(f"goal={goal!r}")
    parts.append(f"tracks={len(tracks)}")
    parts.append(f"tasks={total_tasks}")

    return f"Curriculum({', '.join(parts)})"


def render_and_save(
    curriculum: dict[str, Any],
    output_path: Path | str | None = None,
) -> bool:
    """Render curriculum to Markdown and save to file.

    Args:
        curriculum: Curriculum dict.
        output_path: Output file path. Defaults to project curriculum.md path.

    Returns:
        True if save succeeded.
    """
    if output_path is None:
        output_path = get_curriculum_md_path()

    md_content = render_curriculum_md(curriculum)
    success = write_file(output_path, md_content)

    if success:
        _logger.debug("Rendered curriculum to %s", output_path)
    else:
        _logger.error("Failed to render curriculum to %s", output_path)

    return success
