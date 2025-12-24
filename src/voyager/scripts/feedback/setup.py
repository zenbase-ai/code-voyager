"""Auto-setup feedback collection hooks.

Run: voyager feedback setup

This automatically:
1. Installs PostToolUse hook script into .claude/hooks/
2. Updates project-local settings without overwriting existing hooks
3. Creates the feedback database
4. Validates installation
"""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import typer

from voyager.config import get_feedback_db_path, get_project_dir
from voyager.io import read_json, write_json
from voyager.logging import get_logger

_logger = get_logger("feedback.setup")


HOOK_SCRIPT_CONTENT = '''\
#!/usr/bin/env python3
"""PostToolUse hook — Capture execution feedback for skill refinement.

This hook runs after every tool use to collect execution data.
It stays fast by doing minimal work and deferring analysis.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Guard against recursion
if os.environ.get("VOYAGER_FEEDBACK_HOOK_ACTIVE"):
    sys.exit(0)
os.environ["VOYAGER_FEEDBACK_HOOK_ACTIVE"] = "1"


def main() -> None:
    """Process PostToolUse hook input and log feedback."""
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    session_id = hook_input.get("session_id", "unknown")
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_response = hook_input.get("tool_response", {})
    transcript_path = hook_input.get("transcript_path")

    # Skip if no tool info
    if not tool_name:
        sys.exit(0)

    # Determine success/error
    # Check tool_response for errors (handle both dict and string responses)
    success = True
    error_message = None

    if isinstance(tool_response, dict):
        # Check for explicit error indicators
        if tool_response.get("error"):
            success = False
            error_message = str(tool_response["error"])[:500]
        elif tool_response.get("stderr"):
            stderr = tool_response["stderr"]
            # Some stderr is informational, only mark as error if also has error key
            if tool_response.get("exit_code", 0) != 0:
                success = False
                error_message = str(stderr)[:500]
    elif isinstance(tool_response, str):
        # String response with error indicators
        if "error" in tool_response.lower()[:100]:
            success = False
            error_message = tool_response[:500]

    # Try to detect which skill is being used
    skill_used = None
    try:
        # Add src to path if needed
        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if src_path.exists() and str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from voyager.refinement.detector import SkillDetector

        # Use lightweight detection (no LLM for speed)
        detector = SkillDetector(use_llm=False, llm_timeout=2)
        skill_used = detector.detect(tool_name, tool_input, transcript_path)
    except Exception:
        # Skill detection is best-effort
        pass

    # Log to feedback store
    try:
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
                duration_ms=None,  # Not available in hook
                skill_used=skill_used,
                timestamp=datetime.now(UTC).isoformat(),
            )
        )
    except Exception as e:
        # Log errors to stderr but don't fail the hook
        print(f"Feedback logging error: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
'''


def get_hooks_dir() -> Path:
    """Get the project hooks directory."""
    return get_project_dir() / ".claude" / "hooks"


def get_settings_path() -> Path:
    """Get the project settings file path."""
    project_dir = get_project_dir()

    # Check for existing settings files
    candidates = [
        project_dir / ".claude" / "settings.local.json",
        project_dir / ".claude" / "settings.json",
    ]

    for path in candidates:
        if path.exists():
            return path

    # Default to settings.local.json for project-specific settings
    return project_dir / ".claude" / "settings.local.json"


def install_hook_script(hooks_dir: Path, dry_run: bool = False) -> Path:
    """Install the PostToolUse hook script.

    Args:
        hooks_dir: Directory to install hook into.
        dry_run: If True, don't actually write files.

    Returns:
        Path to the installed hook script.
    """
    hook_path = hooks_dir / "post_tool_use_feedback.py"

    if dry_run:
        typer.echo(f"Would install hook script to: {hook_path}")
        return hook_path

    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(HOOK_SCRIPT_CONTENT)

    # Make executable
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return hook_path


def merge_hooks_config(
    existing: dict[str, Any],
    hook_path: Path,
) -> dict[str, Any]:
    """Merge our hooks with existing config without overwriting.

    Args:
        existing: Existing settings dict.
        hook_path: Path to the installed hook script.

    Returns:
        Updated settings dict.
    """
    our_hook_config = {
        "matcher": "*",  # Match all tools
        "hooks": [
            {
                "type": "command",
                "command": f"python3 '{hook_path}'",
                "timeout": 5000,  # 5 second timeout
            }
        ],
    }

    existing_hooks = existing.get("hooks", {})
    post_tool_hooks = existing_hooks.get("PostToolUse", [])

    # Check if our hook is already installed
    for config in post_tool_hooks:
        for hook in config.get("hooks", []):
            cmd = hook.get("command", "")
            if "post_tool_use_feedback.py" in cmd:
                _logger.info("Feedback hook already installed")
                return existing

    # Add our hook
    post_tool_hooks.append(our_hook_config)
    existing_hooks["PostToolUse"] = post_tool_hooks
    existing["hooks"] = existing_hooks

    return existing


def main(
    db_path: Path | None = None,
    dry_run: bool = False,
    reset: bool = False,
) -> None:
    """Initialize feedback collection.

    Args:
        db_path: Path to the feedback database (defaults to project-local).
        dry_run: If True, show what would be done without making changes.
        reset: If True, reset the database (delete existing data).
    """
    if dry_run:
        typer.echo("Dry run mode - no changes will be made\n")

    # Determine database path
    if db_path is None:
        db_path = get_feedback_db_path()

    typer.echo("Setting up feedback collection...\n")
    typer.echo(f"  Database: {db_path}")

    # Handle reset
    if reset and db_path.exists():
        if dry_run:
            typer.echo("  Would reset database (delete existing data)")
        else:
            from voyager.refinement.store import FeedbackStore

            store = FeedbackStore(db_path)
            store.reset()
            typer.echo("  Reset database")

    # Initialize database
    if not dry_run:
        from voyager.refinement.store import FeedbackStore

        db_path.parent.mkdir(parents=True, exist_ok=True)
        _ = FeedbackStore(db_path)  # Creates tables if needed
        typer.echo("  Initialized database")

    # Install hook script
    hooks_dir = get_hooks_dir()
    typer.echo(f"\n  Hooks dir: {hooks_dir}")

    hook_path = install_hook_script(hooks_dir, dry_run=dry_run)
    if not dry_run:
        typer.echo("  Installed hook script")

    # Update settings
    settings_path = get_settings_path()
    typer.echo(f"\n  Settings: {settings_path}")

    existing: dict[str, Any] = {}
    if settings_path.exists():
        existing = read_json(settings_path) or {}

    updated = merge_hooks_config(existing, hook_path)

    if dry_run:
        typer.echo("  Would update settings with PostToolUse hook")
        typer.echo("\n  Hook configuration:")
        typer.echo(json.dumps(updated.get("hooks", {}), indent=2))
    else:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(settings_path, updated)
        typer.echo("  Updated settings")

    typer.echo("\nSetup complete!")
    typer.echo("\nNext steps:")
    typer.echo("  1. Review hooks with: cat .claude/settings.local.json")
    typer.echo("  2. Use Claude Code normally - feedback is collected automatically")
    typer.echo("  3. View insights with: voyager feedback insights")


if __name__ == "__main__":
    main()
