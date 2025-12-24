"""CLI for proposing new skills from observed patterns.

Analyzes brain state, transcript, or curriculum to identify
repeated workflows that could become reusable skills.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from voyager.brain.store import load_brain
from voyager.config import get_plugin_root, get_voyager_state_dir
from voyager.curriculum.store import load_curriculum
from voyager.factory.store import (
    get_existing_skill_names,
    save_last_update,
    validate_proposals,
)
from voyager.io import read_file, read_json
from voyager.llm import call_claude, is_internal_call
from voyager.logging import get_logger

_logger = get_logger("factory.propose")

app = typer.Typer(
    name="propose",
    help="Propose new skills from observed patterns.",
)


def _load_prompt_template() -> str:
    """Load the propose_skills prompt template."""
    prompt_path = get_plugin_root() / "skills/skill-factory/prompts/propose_skills.prompt.md"
    content = read_file(prompt_path)
    if content is None:
        # Fallback minimal prompt
        return """Analyze the provided context and propose reusable skills.
Write the proposals as valid JSON matching the skill_proposal schema."""
    return content


def _summarize_transcript(transcript_path: Path, max_lines: int = 500) -> str:
    """Summarize transcript for skill pattern detection.

    Args:
        transcript_path: Path to transcript JSONL file.
        max_lines: Maximum lines to read.

    Returns:
        Summarized transcript as string.
    """
    if not transcript_path.exists():
        return ""

    lines = []
    try:
        with transcript_path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                try:
                    entry = json.loads(line.strip())
                    # Extract relevant fields for pattern detection
                    msg_type = entry.get("type", "")
                    if msg_type == "assistant":
                        # Look for tool uses
                        message = entry.get("message", {})
                        content = message.get("content", [])
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "tool_use":
                                    tool_name = block.get("name", "")
                                    lines.append(f"Tool: {tool_name}")
                                elif block.get("type") == "text":
                                    text = block.get("text", "")[:200]
                                    if text:
                                        lines.append(f"Assistant: {text}...")
                    elif msg_type == "user":
                        message = entry.get("message", {})
                        content = message.get("content", "")
                        if isinstance(content, str) and content:
                            lines.append(f"User: {content[:200]}...")
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError as e:
        _logger.warning("Failed to read transcript: %s", e)
        return ""

    return "\n".join(lines[-100:])  # Keep last 100 entries


def _build_propose_prompt(
    brain: dict[str, Any],
    curriculum: dict[str, Any],
    transcript_summary: str,
    existing_skills: set[str],
    output_path: Path,
) -> str:
    """Build the full prompt for skill proposal.

    Args:
        brain: Current brain state.
        curriculum: Current curriculum.
        transcript_summary: Summarized transcript.
        existing_skills: Set of existing skill names to avoid duplicates.
        output_path: Path where proposals JSON should be written.

    Returns:
        Complete prompt string.
    """
    template = _load_prompt_template()
    now = datetime.now(UTC).isoformat()

    parts = [template, "", "---", "", "## Context", ""]

    # Brain state
    if brain.get("project", {}).get("summary"):
        parts.append("### Brain State")
        parts.append("")
        parts.append("```json")
        # Only include relevant parts of brain
        brain_summary = {
            "project": brain.get("project", {}),
            "working_set": brain.get("working_set", {}),
            "decisions": brain.get("decisions", [])[-5:],  # Last 5 decisions
            "progress": {"recent_changes": brain.get("progress", {}).get("recent_changes", [])[-10:]},
        }
        parts.append(json.dumps(brain_summary, indent=2, ensure_ascii=False))
        parts.append("```")
        parts.append("")

    # Curriculum
    if curriculum.get("tracks"):
        parts.append("### Curriculum")
        parts.append("")
        parts.append("```json")
        # Only include track names and task titles
        curriculum_summary = {
            "goal": curriculum.get("goal", ""),
            "tracks": [
                {
                    "name": t.get("name", ""),
                    "tasks": [
                        {"title": task.get("title", ""), "status": task.get("status")}
                        for task in t.get("tasks", [])[:5]
                    ],
                }
                for t in curriculum.get("tracks", [])
            ],
        }
        parts.append(json.dumps(curriculum_summary, indent=2, ensure_ascii=False))
        parts.append("```")
        parts.append("")

    # Transcript summary
    if transcript_summary:
        parts.append("### Recent Session Activity")
        parts.append("")
        parts.append("```")
        parts.append(transcript_summary[:4000])  # Limit size
        parts.append("```")
        parts.append("")

    # Existing skills to avoid
    if existing_skills:
        parts.append("### Existing Skills (do not duplicate)")
        parts.append("")
        parts.append(", ".join(sorted(existing_skills)))
        parts.append("")

    parts.append("## Output")
    parts.append("")
    parts.append(f"Write the skill proposals JSON to: `{output_path}`")
    parts.append("")
    parts.append("## Metadata")
    parts.append("")
    parts.append(f"- Current timestamp: {now}")
    parts.append("")
    parts.append("Use the Write tool to save the proposals JSON file directly.")

    return "\n".join(parts)


@app.callback(invoke_without_command=True)
def main(
    brain_path: Annotated[
        Path | None,
        typer.Option("--brain", "-b", help="Path to brain.json"),
    ] = None,
    curriculum_path: Annotated[
        Path | None,
        typer.Option("--curriculum", "-c", help="Path to curriculum.json"),
    ] = None,
    transcript_path: Annotated[
        Path | None,
        typer.Option("--transcript", "-t", help="Path to transcript JSONL"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output path for proposals JSON"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Print proposals without saving"),
    ] = False,
    skip_llm: Annotated[
        bool,
        typer.Option("--skip-llm", help="Skip LLM call, use existing proposals"),
    ] = False,
) -> None:
    """Propose new skills from observed patterns.

    Analyzes brain state, curriculum, and/or transcript to identify
    repeated workflows that could become reusable skills.
    """
    # Recursion guard
    if is_internal_call():
        _logger.debug("Skipping propose skills (internal call)")
        raise typer.Exit(0)

    _logger.info("Starting skill proposal")

    # Load brain
    brain = load_brain(brain_path)
    _logger.debug("Loaded brain")

    # Load curriculum
    curriculum = load_curriculum(curriculum_path)
    _logger.debug("Loaded curriculum")

    # Summarize transcript if provided
    transcript_summary = ""
    if transcript_path:
        transcript_summary = _summarize_transcript(transcript_path)
        _logger.debug("Summarized transcript (%d chars)", len(transcript_summary))

    # Get existing skills to avoid duplicates
    existing_skills = get_existing_skill_names()
    _logger.debug("Found %d existing generated skills", len(existing_skills))

    # Determine output path
    state_dir = get_voyager_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    proposals_path = output or (state_dir / "skill_proposals.json")

    if skip_llm:
        # Load existing proposals
        proposals = read_json(proposals_path) or {
            "version": 1,
            "proposals": [],
            "metadata": {},
        }
        _logger.info("Skipping LLM, using existing proposals")
    elif dry_run:
        # For dry run, we need to get the proposals without writing
        typer.echo("Dry run not supported with LLM mode", err=True)
        raise typer.Exit(1)
    else:
        # Build prompt and call LLM agent
        prompt = _build_propose_prompt(brain, curriculum, transcript_summary, existing_skills, proposals_path)

        _logger.info("Calling LLM agent to propose skills...")
        result = call_claude(
            prompt,
            cwd=state_dir,
            timeout_seconds=120,
        )

        if result.success and result.files:
            _logger.info("LLM skill proposal successful")
            # Load the written proposals to validate and display
            proposals = read_json(proposals_path)
            if not proposals:
                _logger.error("LLM wrote proposals but file is empty/invalid")
                save_last_update("propose", "failed", error="Invalid proposals file")
                typer.echo("Error: Invalid proposals file written", err=True)
                raise typer.Exit(1)
        else:
            # LLM failed
            _logger.warning("LLM call failed: %s", result.error)
            save_last_update("propose", "failed", error=result.error)
            typer.echo(f"Error: {result.error}", err=True)
            raise typer.Exit(1)

    # Validate proposals
    is_valid, errors = validate_proposals(proposals)
    if not is_valid:
        _logger.warning("Proposals failed validation: %s", errors)
        # Still continue but warn user

    proposal_count = len(proposals.get("proposals", []))

    if dry_run:
        typer.echo(json.dumps(proposals, indent=2, ensure_ascii=False))
        raise typer.Exit(0)

    # Save last update metadata
    save_last_update("propose", "success", proposal_count=proposal_count)

    # Print summary
    typer.echo(f"Proposed {proposal_count} skills:", err=True)
    for p in proposals.get("proposals", []):
        name = p.get("name", "unknown")
        desc = p.get("description", "")[:50]
        typer.echo(f"  - {name}: {desc}...", err=True)


if __name__ == "__main__":
    app()
