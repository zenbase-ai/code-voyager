"""Skill factory commands."""

from pathlib import Path
from typing import Annotated

import typer

from voyager.scripts.factory.propose import main as propose_main
from voyager.scripts.factory.scaffold import list_proposals
from voyager.scripts.factory.scaffold import main as scaffold_main

app = typer.Typer(
    name="factory",
    help="Skill factory (propose and scaffold skills)",
    no_args_is_help=True,
)


@app.command("propose")
def propose(
    brain_path: Annotated[
        Path | None,
        typer.Option("--brain", "-b", help="Path to brain.json"),
    ] = None,
    curriculum_path: Annotated[
        Path | None,
        typer.Option("--curriculum", "-c", help="Path to curriculum.json"),
    ] = None,
    transcript_path: Annotated[
        Path | None,
        typer.Option("--transcript", "-t", help="Path to transcript JSONL"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output path for proposals JSON"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Print proposals without saving"),
    ] = False,
    skip_llm: Annotated[
        bool,
        typer.Option("--skip-llm", help="Skip LLM call, use existing proposals"),
    ] = False,
) -> None:
    """Propose new skills from observed patterns."""
    propose_main(
        brain_path=brain_path,
        curriculum_path=curriculum_path,
        transcript_path=transcript_path,
        output=output,
        dry_run=dry_run,
        skip_llm=skip_llm,
    )


@app.command("scaffold")
def scaffold(
    proposal_name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Name of the proposal to scaffold"),
    ] = None,
    proposal_json: Annotated[
        Path | None,
        typer.Option("--proposal", "-p", help="Path to proposals JSON file"),
    ] = None,
    proposal_index: Annotated[
        int,
        typer.Option("--index", "-i", help="Index of proposal in file (0-based)"),
    ] = 0,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print scaffold without creating files"),
    ] = False,
    skip_llm: Annotated[
        bool,
        typer.Option("--skip-llm", help="Skip LLM, use simple template"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing skill"),
    ] = False,
) -> None:
    """Scaffold a new skill from a proposal."""
    scaffold_main(
        proposal_name=proposal_name,
        proposal_json=proposal_json,
        proposal_index=proposal_index,
        dry_run=dry_run,
        skip_llm=skip_llm,
        force=force,
    )


@app.command("list")
def list_cmd(
    proposal_json: Annotated[
        Path | None,
        typer.Option("--proposal", "-p", help="Path to proposals JSON file"),
    ] = None,
) -> None:
    """List available skill proposals."""
    list_proposals(proposal_json=proposal_json)
