"""Feedback collection and analysis commands."""

from pathlib import Path
from typing import Annotated

import typer

from voyager.scripts.feedback.insights import main as insights_main
from voyager.scripts.feedback.setup import main as setup_main

app = typer.Typer(
    name="feedback",
    help="Feedback collection and analysis",
    no_args_is_help=True,
)


@app.command("setup")
def setup(
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to the feedback database"),
    ] = None,
    reset: Annotated[
        bool,
        typer.Option("--reset", help="Reset the database (deletes existing data)"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show what would be done without changes"),
    ] = False,
) -> None:
    """Initialize feedback collection for skill refinement."""
    setup_main(db_path=db, dry_run=dry_run, reset=reset)


@app.command("insights")
def insights(
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to the feedback database"),
    ] = None,
    skill: Annotated[
        str | None,
        typer.Option("--skill", "-s", help="Filter insights for a specific skill"),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option("--since", help="Only analyze feedback since this date (ISO)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON"),
    ] = False,
    errors: Annotated[
        bool,
        typer.Option("--errors", "-e", help="Show common errors"),
    ] = False,
) -> None:
    """Analyze feedback and generate skill insights."""
    insights_main(
        db_path=db,
        skill=skill,
        since=since,
        json_output=json_output,
        errors=errors,
    )
