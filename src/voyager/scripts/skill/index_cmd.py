"""CLI for building the skill search index.

Usage:
    voyager skill index [--paths PATH...] [--output DIR] [--rebuild] [-v]
    skill-index [options]  # shortcut
"""

from __future__ import annotations

from pathlib import Path

import typer


def main(
    paths: list[Path] | None = None,
    output: Path | None = None,
    rebuild: bool = False,
    skip_llm: bool = False,
    verbose: bool = False,
) -> None:
    """Build or update the skill search index.

    Discovers skills from:
    - Plugin skills: ./skills/
    - Local mirror: ./.claude/skills/local/
    - Generated skills: ./.claude/skills/generated/
    - User skills: ~/.claude/skills/

    Args:
        paths: Additional paths to skill directories to index.
        output: Output directory for the index (default: ~/.skill-index/).
        rebuild: Force rebuild the index from scratch.
        skip_llm: Skip LLM analysis (faster but lower quality).
        verbose: Print progress information.
    """
    from voyager.retrieval.index import SkillIndex

    index = SkillIndex(index_path=output)

    if verbose:
        typer.echo(f"Index path: {index.index_path}")
        if paths:
            typer.echo(f"Additional paths: {paths}")

    try:
        count = index.build(
            skill_roots=paths,
            force=rebuild,
            skip_llm=skip_llm,
            verbose=verbose,
        )

        if count > 0:
            typer.echo(f"Indexed {count} skills")
        elif not rebuild:
            typer.echo("Index already exists. Use --rebuild to recreate.")
        else:
            typer.echo("No skills found to index", err=True)
            raise typer.Exit(1)

    except Exception as e:
        typer.echo(f"Error building index: {e}", err=True)
        raise typer.Exit(1) from None
