"""CLI for generating a curriculum from brain state and repo snapshot.

Reads brain.json and a fresh repo snapshot, invokes the LLM to generate
a structured task backlog, validates the result, and saves the curriculum.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from voyager.brain.store import load_brain
from voyager.config import (
    get_curriculum_json_path,
    get_curriculum_md_path,
    get_plugin_root,
)
from voyager.curriculum.render import render_and_save, render_compact
from voyager.curriculum.store import (
    load_curriculum,
    save_curriculum,
    save_last_update,
)
from voyager.io import read_file, read_json
from voyager.llm import call_claude, is_internal_call
from voyager.logging import get_logger
from voyager.repo.snapshot import snapshot_to_json

_logger = get_logger("curriculum.plan")

app = typer.Typer(
    name="plan",
    help="Generate a curriculum from brain state and repo snapshot.",
)


def _load_prompt_template() -> str:
    """Load the plan_curriculum prompt template."""
    prompt_path = get_plugin_root() / "skills/curriculum-planner/prompts/plan_curriculum.prompt.md"
    content = read_file(prompt_path)
    if content is None:
        # Fallback minimal prompt
        return """Generate a curriculum of tasks for this codebase.
Write the curriculum JSON matching the curriculum schema."""
    return content


def _build_plan_prompt(
    brain: dict[str, Any],
    snapshot: dict[str, Any],
    output_path: Path,
) -> str:
    """Build the full prompt for curriculum planning.

    Args:
        brain: Current brain state.
        snapshot: Repo snapshot.
        output_path: Path where curriculum JSON should be written.

    Returns:
        Complete prompt string.
    """
    template = _load_prompt_template()
    now = datetime.now(UTC).isoformat()

    parts = [template, "", "---", "", "## Brain State", ""]
    parts.append("```json")
    parts.append(json.dumps(brain, indent=2, ensure_ascii=False))
    parts.append("```")
    parts.append("")

    parts.append("## Repo Snapshot")
    parts.append("")
    parts.append("```json")
    # Truncate snapshot if too large
    snapshot_str = json.dumps(snapshot, indent=2, ensure_ascii=False)
    if len(snapshot_str) > 8000:
        snapshot_str = snapshot_str[:8000] + "\n... (truncated)"
    parts.append(snapshot_str)
    parts.append("```")
    parts.append("")

    parts.append("## Output")
    parts.append("")
    parts.append(f"Write the curriculum JSON to: `{output_path}`")
    parts.append("")
    parts.append("## Metadata")
    parts.append("")
    parts.append(f"- Current timestamp: {now}")
    parts.append("")
    parts.append("Use the Write tool to save the curriculum JSON file directly.")

    return "\n".join(parts)


def _count_tasks(curriculum: dict[str, Any]) -> int:
    """Count total tasks in curriculum."""
    return sum(len(track.get("tasks", [])) for track in curriculum.get("tracks", []))


@app.callback(invoke_without_command=True)
def main(
    brain_path: Annotated[
        Path | None,
        typer.Option("--brain", "-b", help="Path to brain.json"),
    ] = None,
    snapshot_path: Annotated[
        Path | None,
        typer.Option("--snapshot", "-s", help="Path to repo snapshot JSON"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output path for curriculum.json"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Print curriculum without saving"),
    ] = False,
    skip_llm: Annotated[
        bool,
        typer.Option("--skip-llm", help="Skip LLM call, just render existing"),
    ] = False,
) -> None:
    """Generate a curriculum from brain state and repo snapshot.

    Reads the brain state and repo snapshot, invokes the LLM to generate
    a structured task backlog, validates the result, and saves the curriculum.
    """
    # Recursion guard
    if is_internal_call():
        _logger.debug("Skipping curriculum plan (internal call)")
        raise typer.Exit(0)

    _logger.info("Starting curriculum planning")

    # Load brain
    brain = load_brain(brain_path)
    brain_session = brain.get("signals", {}).get("last_session_id", "unknown")
    _logger.debug("Loaded brain (session: %s)", brain_session)

    # Generate or load snapshot
    if snapshot_path and snapshot_path.exists():
        snapshot = read_json(snapshot_path) or {}
        _logger.debug("Loaded snapshot from %s", snapshot_path)
    else:
        _logger.info("Generating fresh repo snapshot")
        snapshot = snapshot_to_json()

    # Determine output path
    curriculum_path = output or get_curriculum_json_path()
    md_path = get_curriculum_md_path()

    if skip_llm:
        # Just render existing curriculum
        curriculum = load_curriculum(curriculum_path)
        _logger.info("Skipping LLM, rendering existing curriculum")
    elif dry_run:
        # For dry run, we need to get the curriculum without writing
        typer.echo("Dry run not supported with LLM mode", err=True)
        raise typer.Exit(1)
    else:
        # Build prompt and call LLM agent
        prompt = _build_plan_prompt(brain, snapshot, curriculum_path)

        _logger.info("Calling LLM agent to generate curriculum...")
        result = call_claude(
            prompt,
            cwd=curriculum_path.parent,
            timeout_seconds=180,
        )

        if result.success and result.files:
            _logger.info("LLM curriculum generation successful")
            # Load the written curriculum
            curriculum = read_json(curriculum_path)
            if not curriculum:
                _logger.error("LLM wrote curriculum but file is empty/invalid")
                save_last_update(
                    "failed",
                    error="Invalid curriculum file",
                    brain_session=brain_session,
                )
                typer.echo("Error: Invalid curriculum file written", err=True)
                raise typer.Exit(1)

            # Update metadata
            curriculum.setdefault("metadata", {})
            now = datetime.now(UTC).isoformat()
            curriculum["metadata"]["updated_at"] = now
            if "created_at" not in curriculum["metadata"]:
                curriculum["metadata"]["created_at"] = now
            curriculum["metadata"]["source_brain_session"] = brain_session
            curriculum["metadata"]["total_tasks"] = _count_tasks(curriculum)

            # Re-save with updated metadata
            save_curriculum(curriculum, curriculum_path)
        else:
            # LLM failed
            _logger.warning("LLM call failed: %s", result.error)
            save_last_update(
                "failed",
                error=result.error,
                brain_session=brain_session,
            )
            typer.echo(f"Error: {result.error}", err=True)
            raise typer.Exit(1)

    task_count = _count_tasks(curriculum)

    if dry_run:
        typer.echo(json.dumps(curriculum, indent=2, ensure_ascii=False))
        raise typer.Exit(0)

    # Render curriculum.md
    if render_and_save(curriculum, output_path=md_path):
        _logger.info("Rendered curriculum.md to %s", md_path)

    # Save last update metadata
    save_last_update(
        "success",
        brain_session=brain_session,
        task_count=task_count,
    )

    typer.echo(f"Curriculum generated: {render_compact(curriculum)}", err=True)


if __name__ == "__main__":
    app()
