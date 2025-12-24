"""Curriculum planning commands."""

from pathlib import Path
from typing import Annotated

import typer

from voyager.scripts.curriculum.plan import main as plan_main

app = typer.Typer(
    name="curriculum",
    help="Curriculum planning",
    no_args_is_help=True,
)


@app.command("plan")
def plan(
    brain_path: Annotated[
        Path | None,
        typer.Option("--brain", "-b", help="Path to brain.json"),
    ] = None,
    snapshot_path: Annotated[
        Path | None,
        typer.Option("--snapshot", "-s", help="Path to repo snapshot JSON"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output path for curriculum.json"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Print curriculum without saving"),
    ] = False,
    skip_llm: Annotated[
        bool,
        typer.Option("--skip-llm", help="Skip LLM call, just render existing"),
    ] = False,
) -> None:
    """Generate a curriculum from brain state and repo snapshot."""
    plan_main(
        brain_path=brain_path,
        snapshot_path=snapshot_path,
        output=output,
        dry_run=dry_run,
        skip_llm=skip_llm,
    )
