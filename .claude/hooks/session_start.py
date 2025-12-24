#!/usr/bin/env python3
"""Dogfood wrapper: SessionStart hook for local development.

Delegates to the plugin's session_start.py hook script.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def get_repo_root() -> Path:
    """Get the repository root (parent of .claude)."""
    return Path(__file__).parent.parent.parent


def main() -> None:
    """Delegate to the plugin's session_start hook."""
    repo_root = get_repo_root()
    plugin_hook = repo_root / "scripts" / "hooks" / "session_start.py"

    if not plugin_hook.exists():
        print(json.dumps({"suppressOutput": True}))
        return

    stdin_data = sys.stdin.read()

    try:
        result = subprocess.run(
            [sys.executable, str(plugin_hook)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=10,
            env={
                **os.environ,
                "CLAUDE_PLUGIN_ROOT": str(repo_root),
                "PYTHONPATH": str(repo_root / "src"),
            },
        )

        if result.returncode == 0 and result.stdout.strip():
            print(result.stdout.strip())
        else:
            if result.stderr:
                msg = f"[dogfood] session_start error: {result.stderr}"
                print(msg, file=sys.stderr)
            print(json.dumps({"suppressOutput": True}))

    except Exception as e:
        print(f"[dogfood] session_start exception: {e}", file=sys.stderr)
        print(json.dumps({"suppressOutput": True}))


if __name__ == "__main__":
    main()
