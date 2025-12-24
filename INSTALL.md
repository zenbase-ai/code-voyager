# Installation

## Prerequisites

- [Claude Code](https://claude.ai/code) CLI
- [uv](https://docs.astral.sh/uv/) (recommended for CLI installation)

## Quick Install

```bash
# Install skills to Claude Code
curl -sL https://github.com/zenbase-ai/code-voyager/archive/main.tar.gz | \
  tar -xz -C ~/.claude/skills --strip-components=2 code-voyager-main/skills

# Install the CLI (optional, for advanced features like skill indexing)
uv tool install git+https://github.com/zenbase-ai/code-voyager.git
```

## Install from Source

```bash
# Clone the repo
git clone https://github.com/zenbase-ai/code-voyager.git
cd code-voyager

# Install dependencies
uv sync

# Symlink skills to Claude Code
ln -s "$(pwd)/skills/"* ~/.claude/skills/

# Install CLI globally (optional)
uv tool install -e .
```

## Optional: Semantic Skill Retrieval

For ColBERT-based skill search:

```bash
uv tool install "git+https://github.com/zenbase-ai/code-voyager.git[retrieval]"
```

## Verify Installation

```bash
# Check skills are available
ls ~/.claude/skills/

# Check CLI works (if installed)
voyager --help

# In Claude Code, ask: "What skills are available?"
```

## Development Setup

```bash
# Clone and install with all extras
git clone https://github.com/zenbase-ai/code-voyager.git
cd code-voyager
uv sync --extra dev --extra retrieval

# Run tests
uv run pytest

# Lint
uv run ruff check .
```

## Uninstall

```bash
# Remove skills
rm -rf ~/.claude/skills/session-brain
rm -rf ~/.claude/skills/curriculum-planner
rm -rf ~/.claude/skills/skill-factory
rm -rf ~/.claude/skills/skill-retrieval
rm -rf ~/.claude/skills/skill-refinement

# Remove CLI
uv tool uninstall code-voyager
```
