#!/usr/bin/env python3
"""Thin executable wrapper for calling Claude Code agent from scripts.

This provides a simple CLI interface to the voyager.llm module.

Usage:
    # Run agent with a prompt
    python scripts/lib/claude_print.py "Create a README.md file"

    # With custom working directory
    python scripts/lib/claude_print.py --cwd /path/to/project "Update the config"

Exit codes:
    0: Success
    1: Agent call failed
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from voyager.llm import (
    LLMResult,
    call_claude,
    is_internal_call,
)

app = typer.Typer(
    name="claude-print",
    help="Run Claude Code agent with a prompt.",
    no_args_is_help=True,
)


def _exit_with_result(result: LLMResult) -> None:
    """Print result and exit with appropriate code."""
    if result.success:
        if result.output:
            print(result.output)
        if result.files:
            typer.echo(f"Files written: {', '.join(result.files)}", err=True)
        raise typer.Exit(0)
    else:
        typer.echo(f"Error: {result.error}", err=True)
        raise typer.Exit(1)


@app.command()
def main(
    prompt: Annotated[
        str,
        typer.Argument(help="The prompt to send to Claude"),
    ],
    cwd: Annotated[
        Path | None,
        typer.Option("--cwd", "-c", help="Working directory for the agent"),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Timeout in seconds"),
    ] = 60,
    system: Annotated[
        str | None,
        typer.Option("--system", help="System prompt"),
    ] = None,
) -> None:
    """Run Claude Code agent with the given prompt.

    The agent can read and write files. Use --cwd to set the working directory.
    """
    # Recursion guard: if we're in an internal call, exit silently
    if is_internal_call():
        raise typer.Exit(0)

    result = call_claude(
        prompt,
        cwd=cwd,
        system_prompt=system,
        timeout_seconds=timeout,
    )

    _exit_with_result(result)


if __name__ == "__main__":
    app()
