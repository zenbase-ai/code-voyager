"""Skill indexing and search commands."""

from pathlib import Path
from typing import Annotated

import typer

from voyager.scripts.skill.find import main as find_main
from voyager.scripts.skill.index_cmd import main as index_main

app = typer.Typer(
    name="skill",
    help="Skill indexing and search",
    no_args_is_help=True,
)


@app.command("index")
def index(
    paths: Annotated[
        list[Path] | None,
        typer.Option("--paths", "-p", help="Paths to skill directories to index"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for the index"),
    ] = None,
    rebuild: Annotated[
        bool,
        typer.Option("--rebuild", help="Force rebuild the index from scratch"),
    ] = False,
    skip_llm: Annotated[
        bool,
        typer.Option("--skip-llm", help="Skip LLM analysis (faster but lower quality)"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Print verbose output"),
    ] = False,
) -> None:
    """Build or update the skill search index."""
    index_main(
        paths=paths,
        output=output,
        rebuild=rebuild,
        skip_llm=skip_llm,
        verbose=verbose,
    )


@app.command("find")
def find(
    query: Annotated[
        str | None,
        typer.Argument(help="Search query"),
    ] = None,
    top_k: Annotated[
        int,
        typer.Option("--top-k", "-k", help="Number of results to return"),
    ] = 5,
    index: Annotated[
        Path | None,
        typer.Option("--index", "-i", help="Path to the skill index"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON"),
    ] = False,
) -> None:
    """Search for relevant skills."""
    if not query:
        typer.echo("Error: Missing query argument")
        raise typer.Exit(1)

    find_main(
        query=query,
        top_k=top_k,
        index_path=index,
        json_output=json_output,
    )
