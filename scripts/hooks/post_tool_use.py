#!/usr/bin/env python3
"""PostToolUse hook: collect tool outcomes for skill refinement."""

import contextlib
import json
import os
import sys

# Recursion guard: skip if this is an internal LLM call
if os.environ.get("VOYAGER_FOR_CODE_INTERNAL") == "1":
    sys.exit(0)


def main() -> None:
    """Handle PostToolUse hook event."""
    # Parse hook input from stdin
    with contextlib.suppress(json.JSONDecodeError):
        json.load(sys.stdin)

    # TODO: Implement feedback collection
    # - Extract tool name, inputs, outputs, success/failure
    # - Attribute to active skill(s)
    # - Store in feedback DB

    # For now, silent success
    print(json.dumps({}))


if __name__ == "__main__":
    main()
