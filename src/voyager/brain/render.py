"""Brain renderer for converting brain.json to brain.md.

Produces a deterministic, concise Markdown summary suitable for
context injection. Output is designed to be stable (no reflow noise)
and compact (< 2KB typical).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from voyager.config import get_brain_json_path, get_brain_md_path
from voyager.io import read_json, write_file
from voyager.logging import get_logger

_logger = get_logger("brain.render")


def render_brain_md(brain: dict[str, Any]) -> str:
    """Render brain.json to Markdown format.

    Output is designed to be:
    - Concise (context-friendly)
    - Stable (deterministic ordering, no reflow)
    - Scannable (clear sections, bullet lists)

    Args:
        brain: Brain dict to render.

    Returns:
        Markdown string.
    """
    lines: list[str] = []
    lines.append("# Session Brain")
    lines.append("")

    # Project section
    project = brain.get("project", {})
    summary = project.get("summary", "").strip()
    if summary:
        lines.append(f"**Project:** {summary}")
        lines.append("")

    stack = project.get("stack_guesses", [])
    if stack:
        lines.append(f"**Stack:** {', '.join(stack)}")
        lines.append("")

    commands = project.get("key_commands", [])
    if commands:
        lines.append("**Commands:**")
        for cmd in commands[:5]:  # Limit to 5
            lines.append(f"- `{cmd}`")
        lines.append("")

    # Working set section
    working = brain.get("working_set", {})
    goal = working.get("current_goal", "").strip()
    if goal:
        lines.append("## Current Goal")
        lines.append("")
        lines.append(goal)
        lines.append("")

    plan = working.get("current_plan", [])
    if plan:
        lines.append("**Plan:**")
        for i, step in enumerate(plan[:10], 1):  # Limit to 10
            lines.append(f"{i}. {step}")
        lines.append("")

    questions = working.get("open_questions", [])
    if questions:
        lines.append("**Open questions:**")
        for q in questions[:5]:  # Limit to 5
            lines.append(f"- {q}")
        lines.append("")

    risks = working.get("risks", [])
    if risks:
        lines.append("**Risks:**")
        for r in risks[:5]:  # Limit to 5
            lines.append(f"- {r}")
        lines.append("")

    # Recent decisions (last 3)
    decisions = brain.get("decisions", [])
    if decisions:
        lines.append("## Recent Decisions")
        lines.append("")
        for d in decisions[-3:]:  # Last 3
            decision_text = d.get("decision", "")
            rationale = d.get("rationale", "")
            when = d.get("when", "")
            if decision_text:
                lines.append(f"- **{decision_text}**")
                if rationale:
                    lines.append(f"  - Why: {rationale}")
                if when:
                    lines.append(f"  - When: {when}")
        lines.append("")

    # Progress section
    progress = brain.get("progress", {})
    recent = progress.get("recent_changes", [])
    if recent:
        lines.append("## Recent Changes")
        lines.append("")
        for change in recent[:7]:  # Limit to 7
            lines.append(f"- {change}")
        lines.append("")

    done = progress.get("done", [])
    if done:
        lines.append("**Done:**")
        for item in done[-5:]:  # Last 5
            lines.append(f"- {item}")
        lines.append("")

    # Signals (minimal)
    signals = brain.get("signals", {})
    last_updated = signals.get("last_updated_at", "")
    if last_updated:
        lines.append("---")
        lines.append(f"*Last updated: {last_updated}*")
        lines.append("")

    return "\n".join(lines)


def render_and_save(
    brain: dict[str, Any] | None = None,
    brain_path: Path | str | None = None,
    output_path: Path | str | None = None,
) -> bool:
    """Render brain.json to brain.md and save.

    Args:
        brain: Brain dict. If None, loads from brain_path.
        brain_path: Path to brain.json. Defaults to project path.
        output_path: Path for brain.md. Defaults to project path.

    Returns:
        True if rendering and saving succeeded.
    """
    if brain is None:
        if brain_path is None:
            brain_path = get_brain_json_path()
        brain = read_json(brain_path)
        if brain is None:
            _logger.warning("Could not load brain from %s", brain_path)
            return False

    if output_path is None:
        output_path = get_brain_md_path()

    md_content = render_brain_md(brain)
    success = write_file(output_path, md_content)

    if success:
        _logger.debug("Rendered brain.md to %s", output_path)
    else:
        _logger.error("Failed to write brain.md to %s", output_path)

    return success


def render_compact(brain: dict[str, Any]) -> str:
    """Render a compact one-line summary for logging/debugging.

    Args:
        brain: Brain dict.

    Returns:
        Single-line summary string.
    """
    project = brain.get("project", {})
    working = brain.get("working_set", {})
    progress = brain.get("progress", {})

    parts = []

    summary = project.get("summary", "")[:50]
    if summary:
        parts.append(f"project={summary}")

    goal = working.get("current_goal", "")[:30]
    if goal:
        parts.append(f"goal={goal}")

    n_changes = len(progress.get("recent_changes", []))
    if n_changes:
        parts.append(f"changes={n_changes}")

    n_decisions = len(brain.get("decisions", []))
    if n_decisions:
        parts.append(f"decisions={n_decisions}")

    return " | ".join(parts) if parts else "(empty brain)"
