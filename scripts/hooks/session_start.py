#!/usr/bin/env python3
"""SessionStart hook: inject brain context and repo snapshot.

Uses direct imports from the voyager package instead of subprocess chains.
"""

from __future__ import annotations

import json
import os
import sys

# Recursion guard: skip if this is an internal LLM call
if os.environ.get("VOYAGER_FOR_CODE_INTERNAL") == "1":
    print(json.dumps({"suppressOutput": True}))
    sys.exit(0)

from voyager.scripts.brain.inject import inject_from_stdin


def main() -> None:
    """Handle SessionStart hook event by injecting brain context."""
    try:
        output = inject_from_stdin()
        print(json.dumps(output))
    except Exception as e:
        print(f"inject_context error: {e}", file=sys.stderr)
        fallback = {
            "hookSpecificOutput": {"additionalContext": ""},
            "suppressOutput": True,
        }
        print(json.dumps(fallback))


if __name__ == "__main__":
    main()
