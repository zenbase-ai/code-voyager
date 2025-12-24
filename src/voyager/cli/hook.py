"""Hook handler commands for Claude Code integration.

These commands are designed to be called by Claude Code hooks:
    voyager hook session-start   # SessionStart hook
    voyager hook session-end     # SessionEnd hook
    voyager hook pre-compact     # PreCompact hook
    voyager hook post-tool-use   # PostToolUse hook
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from voyager.llm import is_internal_call
from voyager.scripts.brain.inject import inject_from_stdin
from voyager.scripts.brain.update import main as brain_update_main

app = typer.Typer(
    name="hook",
    help="Claude Code hook handlers",
    no_args_is_help=True,
)


@app.command("session-start")
def session_start() -> None:
    """Handle SessionStart hook - injects brain context.

    Reads hook input JSON from stdin and outputs hook response JSON to stdout.
    Injects the session brain context and repo snapshot into the session.
    """
    # Recursion guard
    if is_internal_call():
        typer.echo(json.dumps({"suppressOutput": True}))
        raise typer.Exit(0)

    try:
        output = inject_from_stdin()
        typer.echo(json.dumps(output))
    except Exception as e:
        print(f"session-start error: {e}", file=sys.stderr)
        fallback = {
            "hookSpecificOutput": {"additionalContext": ""},
            "suppressOutput": True,
        }
        typer.echo(json.dumps(fallback))


@app.command("session-end")
def session_end() -> None:
    """Handle SessionEnd hook - persists session memory.

    Reads hook input JSON from stdin and updates the brain state
    from the transcript when the session ends.
    """
    # Recursion guard
    if is_internal_call():
        typer.echo(json.dumps({}))
        raise typer.Exit(0)

    # Parse hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        hook_input = {}

    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")
    cwd = hook_input.get("cwd", str(Path.cwd()))

    # Resolve transcript path
    transcript = None
    if transcript_path:
        tp = Path(transcript_path)
        if not tp.is_absolute():
            tp = Path(cwd) / tp
        transcript = tp

    try:
        brain_update_main(
            transcript=transcript,
            session_id=session_id,
            snapshot_path=None,
            dry_run=False,
            skip_llm=False,
        )
    except typer.Exit:
        pass  # Normal exit from typer command
    except Exception as e:
        print(f"session-end error: {e}", file=sys.stderr)

    # Always return success to not block the hook
    typer.echo(json.dumps({}))


@app.command("pre-compact")
def pre_compact() -> None:
    """Handle PreCompact hook - persists session memory before compaction.

    Reads hook input JSON from stdin and updates the brain state
    from the transcript before context compaction occurs.
    """
    # Recursion guard
    if is_internal_call():
        typer.echo(json.dumps({}))
        raise typer.Exit(0)

    # Parse hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        hook_input = {}

    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")
    cwd = hook_input.get("cwd", str(Path.cwd()))

    # Resolve transcript path
    transcript = None
    if transcript_path:
        tp = Path(transcript_path)
        if not tp.is_absolute():
            tp = Path(cwd) / tp
        transcript = tp

    try:
        brain_update_main(
            transcript=transcript,
            session_id=session_id,
            snapshot_path=None,
            dry_run=False,
            skip_llm=False,
        )
    except typer.Exit:
        pass  # Normal exit from typer command
    except Exception as e:
        print(f"pre-compact error: {e}", file=sys.stderr)

    # Always return success to not block the hook
    typer.echo(json.dumps({}))


@app.command("post-tool-use")
def post_tool_use() -> None:
    """Handle PostToolUse hook - collects feedback for skill refinement.

    Reads hook input JSON from stdin and logs tool execution data
    for later analysis via `voyager feedback insights`.
    """
    # Recursion guard
    if is_internal_call():
        raise typer.Exit(0)

    # Parse hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        raise typer.Exit(0) from None

    session_id = hook_input.get("session_id", "unknown")
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_response = hook_input.get("tool_response", {})
    transcript_path = hook_input.get("transcript_path")

    # Skip if no tool info
    if not tool_name:
        raise typer.Exit(0)

    # Determine success/error from tool_response
    success = True
    error_message = None

    if isinstance(tool_response, dict):
        if tool_response.get("error"):
            success = False
            error_message = str(tool_response["error"])[:500]
        elif tool_response.get("stderr"):
            if tool_response.get("exit_code", 0) != 0:
                success = False
                error_message = str(tool_response["stderr"])[:500]
    elif isinstance(tool_response, str) and "error" in tool_response.lower()[:100]:
        success = False
        error_message = tool_response[:500]

    # Try to detect which skill is being used (best-effort, no LLM)
    skill_used = None
    try:
        from voyager.refinement.detector import SkillDetector

        detector = SkillDetector(use_llm=True, llm_timeout=30)
        skill_used = detector.detect(tool_name, tool_input, transcript_path)
    except Exception:
        pass  # Skill detection is best-effort

    # Log to feedback store
    try:
        from datetime import UTC, datetime

        from voyager.refinement.store import FeedbackStore, ToolExecution

        store = FeedbackStore()
        store.log_tool_execution(
            ToolExecution(
                session_id=session_id,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_response=tool_response if isinstance(tool_response, dict) else {"output": tool_response},
                success=success,
                error_message=error_message,
                duration_ms=None,
                skill_used=skill_used,
                timestamp=datetime.now(UTC).isoformat(),
            )
        )
    except Exception as e:
        print(f"Feedback logging error: {e}", file=sys.stderr)

    raise typer.Exit(0)
