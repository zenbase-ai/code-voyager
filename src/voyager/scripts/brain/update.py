"""CLI for updating the Session Brain from a transcript.

Reads a session transcript (JSONL), invokes the LLM to update brain.json,
validates the result, renders brain.md, and saves an episode snapshot.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from voyager.brain.render import render_and_save, render_compact
from voyager.brain.store import (
    load_brain,
    save_brain,
    save_episode,
    save_last_update,
)
from voyager.config import get_brain_json_path, get_brain_md_path, get_plugin_root
from voyager.io import read_file, read_json, read_jsonl
from voyager.llm import call_claude, is_internal_call
from voyager.logging import get_logger

_logger = get_logger("update_brain")

app = typer.Typer(
    name="update",
    help="Update Session Brain from a transcript.",
)

# Limits to keep prompts bounded
MAX_TRANSCRIPT_LINES = 200
MAX_TRANSCRIPT_CHARS = 50000


def _load_prompt_template() -> str:
    """Load the update_brain prompt template."""
    prompt_path = get_plugin_root() / "skills/session-brain/prompts/update_brain.prompt.md"
    content = read_file(prompt_path)
    if content is None:
        # Fallback minimal prompt
        return """Update the brain JSON based on the transcript.
Write the updated brain JSON matching the brain schema."""
    return content


def _format_transcript_for_prompt(
    lines: list[dict[str, Any]],
    max_lines: int = MAX_TRANSCRIPT_LINES,
    max_chars: int = MAX_TRANSCRIPT_CHARS,
) -> str:
    """Format transcript lines for LLM prompt.

    Truncates to stay within bounds while keeping recent context.

    Args:
        lines: Parsed transcript lines.
        max_lines: Maximum lines to include.
        max_chars: Maximum characters in output.

    Returns:
        Formatted transcript string.
    """
    if not lines:
        return "(empty transcript)"

    # Take last N lines (most recent context is most relevant)
    recent = lines[-max_lines:]

    formatted = []
    total_chars = 0

    for entry in recent:
        # Format based on entry type
        entry_type = entry.get("type", "unknown")
        content = ""

        if entry_type == "user":
            message = entry.get("message", "")
            content = f"USER: {message}"
        elif entry_type == "assistant":
            message = entry.get("message", "")
            content = f"ASSISTANT: {message[:500]}"  # Truncate long responses
        elif entry_type == "tool_use":
            tool = entry.get("tool", "")
            content = f"TOOL: {tool}"
        elif entry_type == "tool_result":
            tool = entry.get("tool", "")
            content = f"RESULT: {tool} completed"
        else:
            # Generic format
            content = json.dumps(entry, ensure_ascii=False)[:200]

        if total_chars + len(content) > max_chars:
            break

        formatted.append(content)
        total_chars += len(content) + 1

    return "\n".join(formatted)


def _build_update_prompt(
    current_brain: dict[str, Any],
    transcript_text: str,
    snapshot: dict[str, Any] | None,
    session_id: str,
    output_path: Path,
) -> str:
    """Build the full prompt for brain update.

    Args:
        current_brain: Current brain state.
        transcript_text: Formatted transcript.
        snapshot: Optional repo snapshot.
        session_id: Session identifier.
        output_path: Path where brain JSON should be written.

    Returns:
        Complete prompt string.
    """
    template = _load_prompt_template()
    now = datetime.now(UTC).isoformat()

    parts = [template, "", "---", "", "## Current Brain", ""]
    parts.append("```json")
    parts.append(json.dumps(current_brain, indent=2, ensure_ascii=False))
    parts.append("```")
    parts.append("")

    parts.append("## Session Transcript")
    parts.append("")
    parts.append("```")
    parts.append(transcript_text)
    parts.append("```")
    parts.append("")

    if snapshot:
        parts.append("## Repo Snapshot")
        parts.append("")
        parts.append("```json")
        parts.append(json.dumps(snapshot, indent=2, ensure_ascii=False)[:5000])
        parts.append("```")
        parts.append("")

    parts.append("## Output")
    parts.append("")
    parts.append(f"Write the updated brain JSON to: `{output_path}`")
    parts.append("")
    parts.append("## Metadata")
    parts.append("")
    parts.append(f"- Session ID: {session_id}")
    parts.append(f"- Current timestamp: {now}")
    parts.append("")
    parts.append("Use the Write tool to save the brain JSON file directly.")

    return "\n".join(parts)


@app.callback(invoke_without_command=True)
def main(
    transcript: Annotated[
        Path | None,
        typer.Option("--transcript", "-t", help="Path to transcript JSONL file"),
    ] = None,
    session_id: Annotated[
        str,
        typer.Option("--session-id", "-s", help="Session identifier"),
    ] = "",
    snapshot_path: Annotated[
        Path | None,
        typer.Option("--snapshot", help="Path to repo snapshot JSON"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Print updated brain without saving"),
    ] = False,
    skip_llm: Annotated[
        bool,
        typer.Option("--skip-llm", help="Skip LLM call, just update timestamps"),
    ] = False,
) -> None:
    """Update the Session Brain from a transcript.

    Reads the transcript, invokes the LLM to produce an updated brain,
    validates the result, and saves brain.json + brain.md + episode file.
    """
    # Recursion guard
    if is_internal_call():
        _logger.debug("Skipping update_brain (internal call)")
        raise typer.Exit(0)

    # Generate session_id if not provided
    if not session_id:
        session_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    _logger.info("Updating brain for session %s", session_id)

    # Load current brain
    current_brain = load_brain()
    _logger.debug("Loaded brain: %s", render_compact(current_brain))

    # Read transcript
    transcript_lines: list[dict[str, Any]] = []
    total_lines = 0
    if transcript and transcript.exists():
        result = read_jsonl(transcript)
        total_lines = result.total_lines
        if result.invalid_lines:
            _logger.warning(
                "Skipped %d invalid transcript line(s) in %s",
                result.invalid_lines,
                transcript,
            )
        transcript_lines = [item for item in result.items if isinstance(item, dict)]
        _logger.info("Read %d transcript line(s) from %s", total_lines, transcript)
    else:
        _logger.warning("No transcript provided or file not found")

    # Read snapshot if provided
    snapshot: dict[str, Any] | None = None
    if snapshot_path and snapshot_path.exists():
        snapshot = read_json(snapshot_path)
        _logger.debug("Loaded snapshot from %s", snapshot_path)

    # Determine output path
    brain_path = get_brain_json_path()

    # Determine if we should call LLM
    if skip_llm or not transcript_lines:
        # Minimal update: just update timestamps
        _logger.info("Skipping LLM call, minimal update only")
        updated_brain = current_brain.copy()
        updated_brain["signals"] = {
            "last_session_id": session_id,
            "last_updated_at": datetime.now(UTC).isoformat(),
        }
        status = "skipped"
        error = "No transcript or LLM skipped"
    elif dry_run:
        # For dry run, we need to get the brain without writing
        typer.echo("Dry run not supported with LLM mode", err=True)
        raise typer.Exit(1)
    else:
        # Build prompt and call LLM agent
        transcript_text = _format_transcript_for_prompt(transcript_lines)
        prompt = _build_update_prompt(current_brain, transcript_text, snapshot, session_id, brain_path)

        _logger.info("Calling LLM agent to update brain...")
        result = call_claude(
            prompt,
            cwd=brain_path.parent,
            timeout_seconds=120,
        )

        if result.success and result.files:
            _logger.info("LLM update successful")
            # Load the written brain
            updated_brain = read_json(brain_path)
            if not updated_brain:
                _logger.error("LLM wrote brain but file is empty/invalid")
                save_last_update(session_id, "failed", error="Invalid brain file written")
                typer.echo("Error: Invalid brain file written", err=True)
                raise typer.Exit(1)

            # Ensure signals are updated
            updated_brain.setdefault("signals", {})
            updated_brain["signals"]["last_session_id"] = session_id
            updated_brain["signals"]["last_updated_at"] = datetime.now(UTC).isoformat()

            # Re-save with updated signals
            save_brain(updated_brain, brain_path)
            status = "success"
            error = None
        else:
            # LLM failed, do minimal update
            _logger.warning("LLM call failed: %s", result.error)
            updated_brain = current_brain.copy()
            updated_brain["signals"] = {
                "last_session_id": session_id,
                "last_updated_at": datetime.now(UTC).isoformat(),
            }
            # Add a note about the failed update
            progress = updated_brain.setdefault("progress", {})
            recent = progress.setdefault("recent_changes", [])
            recent.insert(0, f"[{session_id}] Brain update failed: {result.error}")
            recent = recent[:10]  # Keep bounded
            progress["recent_changes"] = recent
            status = "failed"
            error = result.error

    if dry_run:
        typer.echo(json.dumps(updated_brain, indent=2, ensure_ascii=False))
        raise typer.Exit(0)

    # Save brain.json (if not already saved by LLM)
    if status != "success":
        if save_brain(updated_brain, brain_path):
            _logger.info("Saved brain to %s", brain_path)
        else:
            _logger.error("Failed to save brain")
            save_last_update(session_id, "failed", error="Failed to save brain.json")
            raise typer.Exit(1)

    # Render brain.md
    md_path = get_brain_md_path()
    if render_and_save(updated_brain, output_path=md_path):
        _logger.info("Rendered brain.md to %s", md_path)

    # Save episode
    episode_path = save_episode(updated_brain, session_id)
    if episode_path:
        _logger.info("Saved episode to %s", episode_path)

    # Save last update metadata
    save_last_update(
        session_id,
        status,
        error=error,
        transcript_lines=total_lines,
    )

    typer.echo(f"Brain updated: {render_compact(updated_brain)}", err=True)


if __name__ == "__main__":
    app()
