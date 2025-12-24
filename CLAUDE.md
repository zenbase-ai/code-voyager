# Voyager Development Guidelines

## CLI Framework

Use **typer** for all CLI tools in this project (not argparse).

Pattern for CLI commands:

```python
from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(name="my-command", help="Description")

@app.command()
def main(
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Path to something"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Print verbose output"),
    ] = False,
) -> None:
    """Command description."""
    typer.echo("Output")

if __name__ == "__main__":
    app()
```

## Code Style

- Python 3.13+
- Use `Path` objects for file paths
- Type hints on all functions
- Use `from __future__ import annotations` for forward references
- Use `just lint` to lint and `just fmt` to autoformat code (uses ruff)
- Test with `uv run pytest`
