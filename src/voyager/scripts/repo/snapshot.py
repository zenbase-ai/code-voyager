"""CLI for generating repo snapshots.

Produces a compact JSON snapshot of the current repository state,
suitable for injection into Session Brain and Curriculum Planner contexts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from voyager.io import write_file
from voyager.repo.snapshot import snapshot_to_json

app = typer.Typer(
    name="snapshot",
    help="Generate a compact repo snapshot as JSON.",
)


@app.callback(invoke_without_command=True)
def main(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Repository root path (defaults to cwd)"),
    ] = None,
    compact: Annotated[
        bool,
        typer.Option("--compact", "-c", help="Output compact JSON (no indentation)"),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write output to file instead of stdout"),
    ] = None,
) -> None:
    """Generate a repo snapshot as JSON.

    Collects git status, file structure, and run hints into a compact
    JSON object suitable for context injection.
    """
    snapshot = snapshot_to_json(path)

    indent = None if compact else 2
    json_output = json.dumps(snapshot, indent=indent, ensure_ascii=False)

    if output:
        if not write_file(output, json_output + "\n"):
            raise typer.Exit(1)
        typer.echo(f"Snapshot written to {output}", err=True)
    else:
        typer.echo(json_output)


if __name__ == "__main__":
    app()
