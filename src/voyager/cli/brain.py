"""Brain management commands."""

from pathlib import Path
from typing import Annotated

import typer

from voyager.scripts.brain.inject import main as inject_main
from voyager.scripts.brain.update import main as update_main

app = typer.Typer(
    name="brain",
    help="Session brain management",
    no_args_is_help=True,
)


@app.command("update")
def update(
    transcript: Annotated[
        Path | None,
        typer.Option("--transcript", "-t", help="Path to transcript JSONL file"),
    ] = None,
    session_id: Annotated[
        str,
        typer.Option("--session-id", "-s", help="Session identifier"),
    ] = "",
    snapshot_path: Annotated[
        Path | None,
        typer.Option("--snapshot", help="Path to repo snapshot JSON"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Print updated brain without saving"),
    ] = False,
    skip_llm: Annotated[
        bool,
        typer.Option("--skip-llm", help="Skip LLM call, just update timestamps"),
    ] = False,
) -> None:
    """Update the Session Brain from a transcript."""
    update_main(
        transcript=transcript,
        session_id=session_id,
        snapshot_path=snapshot_path,
        dry_run=dry_run,
        skip_llm=skip_llm,
    )


@app.command("inject")
def inject(
    from_stdin: Annotated[
        bool,
        typer.Option("--stdin", help="Read hook input from stdin"),
    ] = False,
    brain_path: Annotated[
        Path | None,
        typer.Option("--brain", "-b", help="Path to brain.md"),
    ] = None,
    snapshot_path: Annotated[
        Path | None,
        typer.Option("--snapshot", "-s", help="Path to repo snapshot JSON"),
    ] = None,
    repo_path: Annotated[
        Path | None,
        typer.Option("--repo", "-r", help="Repo path for snapshot generation"),
    ] = None,
) -> None:
    """Inject brain context at SessionStart."""
    inject_main(
        from_stdin=from_stdin,
        brain_path=brain_path,
        snapshot_path=snapshot_path,
        repo_path=repo_path,
    )
