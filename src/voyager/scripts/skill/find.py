"""CLI for searching skills.

Usage:
    voyager skill find "query" [--top-k N] [--index DIR] [--json]
    find-skill "query" [options]  # shortcut
"""

from __future__ import annotations

import json as json_module
from pathlib import Path

import typer


def main(
    query: str,
    top_k: int = 5,
    index_path: Path | None = None,
    json_output: bool = False,
) -> None:
    """Search for relevant skills.

    Args:
        query: Natural language search query.
        top_k: Number of results to return.
        index_path: Path to the skill index (default: ~/.skill-index/).
        json_output: Output results as JSON.
    """
    from voyager.retrieval.index import SkillIndex

    index = SkillIndex(index_path=index_path)

    try:
        results = index.search(query, k=top_k)

        if json_output:
            output = [
                {
                    "skill_id": r.skill_id,
                    "name": r.name,
                    "purpose": r.purpose,
                    "path": r.path,
                    "score": r.score,
                    "file_types": r.file_types,
                    "capabilities": r.capabilities,
                }
                for r in results
            ]
            typer.echo(json_module.dumps(output, indent=2))
        else:
            if not results:
                typer.echo(f'No skills found matching: "{query}"')
                return

            typer.echo(f'\nSkills matching: "{query}"\n')
            for i, r in enumerate(results, 1):
                typer.echo(f"{i}. {r.name} (score: {r.score:.3f})")
                if r.purpose:
                    # Truncate purpose to ~80 chars
                    purpose = r.purpose[:80] + "..." if len(r.purpose) > 80 else r.purpose
                    typer.echo(f"   {purpose}")
                typer.echo(f"   Path: {r.path}")
                typer.echo()

    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None
    except Exception as e:
        typer.echo(f"Error searching: {e}", err=True)
        raise typer.Exit(1) from None
