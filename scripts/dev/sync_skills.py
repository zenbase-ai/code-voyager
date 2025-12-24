#!/usr/bin/env python3
"""Sync plugin skills to local development mirror.

Copies skills from the plugin's skills/ directory to .claude/skills/local/
for local development and testing without installing the plugin.
"""

import shutil
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="sync-skills",
    help="Sync plugin skills to local development mirror",
)


def get_repo_root() -> Path:
    """Find the repository root (directory containing .git)."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    # Fallback to cwd if not in a git repo
    return Path.cwd()


def sync_skills(
    source: Path | None = None,
    dest: Path | None = None,
    *,
    clean: bool = False,
    verbose: bool = False,
) -> int:
    """Sync skills from source to destination.

    Args:
        source: Source skills directory (default: <repo>/skills/)
        dest: Destination directory (default: <repo>/.claude/skills/local/)
        clean: Remove destination before syncing
        verbose: Print verbose output

    Returns:
        Exit code (0 for success)
    """
    repo_root = get_repo_root()

    if source is None:
        source = repo_root / "skills"
    if dest is None:
        dest = repo_root / ".claude" / "skills" / "local"

    if not source.exists():
        typer.echo(f"Error: Source directory does not exist: {source}", err=True)
        return 1

    if verbose:
        typer.echo(f"Syncing skills from {source} to {dest}")

    # Clean destination if requested
    if clean and dest.exists():
        if verbose:
            typer.echo(f"Cleaning destination: {dest}")
        shutil.rmtree(dest)

    # Create destination if it doesn't exist
    dest.mkdir(parents=True, exist_ok=True)

    # Copy each skill directory
    synced = 0
    for skill_dir in source.iterdir():
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            dest_skill = dest / skill_dir.name
            if dest_skill.exists():
                shutil.rmtree(dest_skill)
            shutil.copytree(skill_dir, dest_skill)
            synced += 1
            if verbose:
                typer.echo(f"  Synced: {skill_dir.name}")

    typer.echo(f"Synced {synced} skill(s) to {dest}")
    return 0


@app.command()
def main(
    source: Annotated[
        Path | None,
        typer.Option("--source", "-s", help="Source skills directory (default: <repo>/skills/)"),
    ] = None,
    dest: Annotated[
        Path | None,
        typer.Option(
            "--dest",
            "-d",
            help="Destination directory (default: <repo>/.claude/skills/local/)",
        ),
    ] = None,
    clean: Annotated[
        bool,
        typer.Option("--clean", "-c", help="Remove destination before syncing"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Print verbose output"),
    ] = False,
) -> None:
    """Sync plugin skills to local development mirror."""
    exit_code = sync_skills(
        source=source,
        dest=dest,
        clean=clean,
        verbose=verbose,
    )
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
