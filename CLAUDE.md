# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
just lint          # Lint with ruff (check + format --check)
just fmt           # Autoformat with ruff
uv run pytest -q   # Run tests
uv run pytest -q tests/test_foo.py::test_bar  # Run single test
```

### CLI (voyager)

```bash
voyager --help                    # Show all commands
voyager brain update              # Update brain from transcript
voyager brain inject              # Inject brain context (for hooks)
voyager curriculum plan           # Generate curriculum
voyager repo snapshot             # Generate repo snapshot
voyager factory propose           # Propose new skills
voyager factory scaffold          # Scaffold a skill
voyager skill index               # Build ColBERT skill index
voyager skill find "query"        # Search skills
voyager feedback insights         # Show skill insights
voyager hook session-start        # Hook handlers (read from stdin)
```

### Hook Testing (fixture-driven)

```bash
just hook-session-start    # Test SessionStart hook
just hook-pre-compact      # Test PreCompact hook
just hook-session-end      # Test SessionEnd hook
```

## Architecture

### Module Structure

```
src/voyager/
├── cli/           # Typer CLI entry points (thin wrappers)
├── scripts/       # Business logic for each CLI command
├── brain/         # Session Brain: store, render, update
├── curriculum/    # Curriculum Planner: store, render
├── factory/       # Skill Factory: proposals, scaffolding
├── retrieval/     # ColBERT skill search: index, embedding, discovery
├── refinement/    # Skill Refinement: feedback store, detector
├── repo/          # Repo snapshot generation
├── llm.py         # Claude Agent SDK wrapper (call_claude)
├── io.py          # Safe atomic I/O (read/write JSON/JSONL)
└── jsonschema.py  # Schema validation utilities
```

### Key Patterns

**CLI → Scripts separation**: CLI modules in `cli/` are thin typer wrappers that delegate to `scripts/` for logic. This keeps CLI code testable and allows reuse.

**LLM calls via `call_claude()`**: All LLM interactions go through `voyager.llm.call_claude()`, which:
- Sets `VOYAGER_FOR_CODE_INTERNAL=1` recursion guard
- Uses Claude Agent SDK with restricted tools (Read, Write, Glob by default)
- Returns `LLMResult` dataclass with success/output/files/error

**Safe I/O via `voyager.io`**: All file operations use helpers from `io.py`:
- `read_json()` / `write_json()` - graceful defaults, atomic writes
- `read_jsonl()` / `write_jsonl()` - for transcripts
- Never raises on missing files

**Hook handlers**: `cli/hook.py` implements Claude Code hooks:
- Read JSON from stdin, output JSON to stdout
- All hooks check `is_internal_call()` recursion guard first
- Never crash - return fallback response on error

### Artifact Locations

All runtime state lives under `.claude/voyager/`:
- `brain.json` / `brain.md` - Session brain state
- `curriculum.json` / `curriculum.md` - Curriculum plans
- `skill_proposals.json` - Pending skill proposals
- `feedback.db` - SQLite feedback store
- `skill-index/` - ColBERT index

## CLI Framework

Use **typer** for all CLI tools (not argparse).

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
```

## Code Style

- Python 3.13+
- Use `Path` objects for file paths
- Type hints on all functions
- Use `from __future__ import annotations` for forward references
