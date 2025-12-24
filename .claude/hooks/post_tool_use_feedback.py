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
    elif isinstance(tool_response, str) and "error" in tool_response.lower()[:100]:
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
