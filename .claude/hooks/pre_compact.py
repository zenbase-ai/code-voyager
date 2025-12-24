#!/usr/bin/env python3
"""Dogfood wrapper: PreCompact hook for local development.

Delegates to the plugin's pre_compact.py hook script.
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
    """Delegate to the plugin's pre_compact hook."""
    repo_root = get_repo_root()
    plugin_hook = repo_root / "scripts" / "hooks" / "pre_compact.py"

    if not plugin_hook.exists():
        print(json.dumps({}))
        return

    stdin_data = sys.stdin.read()

    try:
        result = subprocess.run(
            [sys.executable, str(plugin_hook)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=20,
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
                print(f"[dogfood] pre_compact error: {result.stderr}", file=sys.stderr)
            print(json.dumps({}))

    except Exception as e:
        print(f"[dogfood] pre_compact exception: {e}", file=sys.stderr)
        print(json.dumps({}))


if __name__ == "__main__":
    main()
