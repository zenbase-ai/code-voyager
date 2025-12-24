"""CLI for injecting brain context at SessionStart.

Reads brain.md (if exists) and generates a repo snapshot to inject
as additionalContext into the session. This runs fast without LLM calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from voyager.config import get_brain_json_path, get_brain_md_path, get_voyager_state_dir
from voyager.io import read_file, read_json
from voyager.llm import is_internal_call
from voyager.logging import get_logger
from voyager.repo.snapshot import snapshot_to_json

_logger = get_logger("inject_context")

app = typer.Typer(
    name="inject",
    help="Inject brain context at SessionStart.",
)


def _render_snapshot_compact(snapshot: dict[str, Any]) -> str:
    """Render repo snapshot to a compact text format.

    Args:
        snapshot: Repo snapshot dict.

    Returns:
        Compact text representation.
    """
    lines: list[str] = []

    # Git info
    git = snapshot.get("git", {})
    branch = git.get("branch")
    if branch:
        lines.append(f"Branch: {branch}")

    status = git.get("status", [])
    if status:
        lines.append(f"Modified: {len(status)} file(s)")

    # Top-level structure
    files = snapshot.get("files", {})
    tree = files.get("tree")
    if isinstance(tree, str) and tree.strip():
        lines.append("Tree:")
        for line in tree.splitlines()[:40]:
            lines.append(f"  {line}")
    else:
        top_level = files.get("top_level", [])
        if top_level:
            dirs = [e["name"] for e in top_level if e.get("type") == "dir"][:10]
            files_list = [e["name"] for e in top_level if e.get("type") == "file"][:5]
            if dirs:
                lines.append(f"Dirs: {', '.join(dirs)}")
            if files_list:
                lines.append(f"Files: {', '.join(files_list)}")

    # Run hints
    hints = snapshot.get("run_hints", [])
    if hints:
        lines.append("Hints:")
        for hint in hints[:5]:
            lines.append(f"  {hint[:100]}")

    return "\n".join(lines) if lines else "(empty snapshot)"


def _get_next_actions(brain: dict[str, Any]) -> list[str]:
    """Extract next actions from brain state.

    Args:
        brain: Brain dict.

    Returns:
        List of next action strings.
    """
    actions: list[str] = []

    # Get from current plan
    working = brain.get("working_set", {})
    plan = working.get("current_plan", [])
    if plan:
        for step in plan[:3]:
            if isinstance(step, str):
                actions.append(step)

    # Add open questions as implicit actions
    questions = working.get("open_questions", [])
    if questions and len(actions) < 3:
        for q in questions[:2]:
            if isinstance(q, str) and len(actions) < 3:
                actions.append(f"Resolve: {q}")

    return actions[:3]


def build_context(
    brain_md: str | None,
    brain: dict[str, Any] | None,
    snapshot: dict[str, Any],
) -> str:
    """Build the additionalContext string for injection.

    Args:
        brain_md: Brain markdown content (or None).
        brain: Brain JSON dict (or None).
        snapshot: Repo snapshot dict.

    Returns:
        Context string for injection.
    """
    sections: list[str] = []

    # Session Brain section
    if brain_md and brain_md.strip():
        sections.append("## Session Brain")
        sections.append("")
        sections.append(brain_md.strip())
        sections.append("")

    # Next actions (if available)
    if brain:
        actions = _get_next_actions(brain)
        if actions:
            sections.append("## Suggested Next Actions")
            sections.append("")
            for i, action in enumerate(actions, 1):
                sections.append(f"{i}. {action}")
            sections.append("")

    # Repo snapshot section
    sections.append("## Repo Snapshot")
    sections.append("")
    sections.append(_render_snapshot_compact(snapshot))
    sections.append("")

    return "\n".join(sections)


def inject_from_stdin() -> dict[str, Any]:
    """Read hook input from stdin and produce injection output.

    Returns:
        Hook output dict with additionalContext.
    """
    # Parse hook input
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        hook_input = {}

    cwd = hook_input.get("cwd", str(Path.cwd()))
    session_id = hook_input.get("session_id", "")

    _logger.debug("SessionStart for session=%s cwd=%s", session_id, cwd)

    # Ensure voyager state dir exists
    state_dir = get_voyager_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    # Read brain.md
    brain_md_path = get_brain_md_path()
    brain_md = read_file(brain_md_path)

    # Read brain.json for next actions
    brain_json_path = get_brain_json_path()
    brain = read_json(brain_json_path)

    # Generate repo snapshot
    snapshot = snapshot_to_json(cwd)

    # Build context
    context = build_context(brain_md, brain, snapshot)

    # Build output
    output: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        },
        "suppressOutput": True,
    }

    return output


@app.callback(invoke_without_command=True)
def main(
    from_stdin: Annotated[
        bool,
        typer.Option("--stdin", help="Read hook input from stdin"),
    ] = False,
    brain_path: Annotated[
        Path | None,
        typer.Option("--brain", "-b", help="Path to brain.md"),
    ] = None,
    snapshot_path: Annotated[
        Path | None,
        typer.Option("--snapshot", "-s", help="Path to repo snapshot JSON"),
    ] = None,
    repo_path: Annotated[
        Path | None,
        typer.Option("--repo", "-r", help="Repo path for snapshot generation"),
    ] = None,
) -> None:
    """Inject brain context at SessionStart.

    When called with --stdin, reads hook input JSON from stdin and outputs
    hook response JSON to stdout. Otherwise, accepts explicit paths.
    """
    # Recursion guard
    if is_internal_call():
        _logger.debug("Skipping inject_context (internal call)")
        typer.echo(json.dumps({"suppressOutput": True}))
        raise typer.Exit(0)

    if from_stdin:
        output = inject_from_stdin()
        typer.echo(json.dumps(output))
        raise typer.Exit(0)

    # Manual mode: use explicit paths
    brain_md = None
    if brain_path and brain_path.exists():
        brain_md = read_file(brain_path)

    brain = None
    brain_json_path = get_brain_json_path()
    if brain_json_path.exists():
        brain = read_json(brain_json_path)

    snapshot: dict[str, Any]
    if snapshot_path and snapshot_path.exists():
        snapshot = read_json(snapshot_path) or {}
    else:
        snapshot = snapshot_to_json(repo_path or Path.cwd())

    context = build_context(brain_md, brain, snapshot)
    output = {
        "hookSpecificOutput": {
            "additionalContext": context,
        },
        "suppressOutput": True,
    }

    typer.echo(json.dumps(output, indent=2))


if __name__ == "__main__":
    app()
