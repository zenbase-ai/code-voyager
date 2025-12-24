"""Repository utility commands."""

from pathlib import Path
from typing import Annotated

import typer

from voyager.scripts.repo.snapshot import main as snapshot_main

app = typer.Typer(
    name="repo",
    help="Repository utilities",
    no_args_is_help=True,
)


@app.command("snapshot")
def snapshot(
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
    """Generate a repo snapshot as JSON."""
    snapshot_main(path=path, compact=compact, output=output)
