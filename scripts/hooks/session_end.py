#!/usr/bin/env python3
"""SessionEnd hook: persist session memory when session ends.

Calls the brain update logic directly to update the brain state
from the transcript when the session ends.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Recursion guard: skip if this is an internal LLM call
if os.environ.get("VOYAGER_FOR_CODE_INTERNAL") == "1":
    print(json.dumps({}))
    sys.exit(0)

import typer

from voyager.scripts.brain.update import main as brain_update_main


def main() -> None:
    """Handle SessionEnd hook event by updating the brain."""
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
        # Call brain update directly
        brain_update_main(
            transcript=transcript,
            session_id=session_id,
            snapshot_path=None,
            dry_run=False,
            skip_llm=False,
        )
    except typer.Exit:
        # Normal exit from typer command
        pass
    except Exception as e:
        print(f"update_brain error: {e}", file=sys.stderr)

    # Always return success to not block the hook
    print(json.dumps({}))


if __name__ == "__main__":
    main()
