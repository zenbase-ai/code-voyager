# Installation

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- [Claude Code](https://claude.ai/code) CLI

## Quick Start

```bash
# Clone the repo
git clone https://github.com/zenbase-ai/voyager.git
cd voyager

# Install dependencies
uv sync

# Install as a Claude Code plugin
claude plugins add .
```

## Optional: Semantic Skill Retrieval

For ColBERT-based skill search:

```bash
uv sync --extra retrieval
```

## Verify Installation

```bash
# Check the CLI works
uv run voyager --help

# Check skills are available in Claude Code
claude
# Then ask: "What skills are available?"
```

## Development Setup

```bash
# Install dev + retrieval extras
uv sync --extra dev --extra retrieval

# Run tests
uv run pytest

# Lint
uv run ruff check .
```
