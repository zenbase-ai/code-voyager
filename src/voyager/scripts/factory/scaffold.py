"""CLI for scaffolding a new skill from a proposal.

Takes a skill proposal and generates the skill folder with
SKILL.md and any necessary reference files.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from voyager.config import get_plugin_root, get_voyager_state_dir
from voyager.factory.store import (
    add_skill_to_index,
    get_skill_folder_path,
    save_last_update,
    skill_exists,
)
from voyager.io import read_file, read_json, write_file
from voyager.llm import call_claude, is_internal_call
from voyager.logging import get_logger

_logger = get_logger("factory.scaffold")

app = typer.Typer(
    name="scaffold",
    help="Scaffold a new skill from a proposal.",
)


def _load_prompt_template() -> str:
    """Load the scaffold_skill prompt template."""
    prompt_path = get_plugin_root() / "skills/skill-factory/prompts/scaffold_skill.prompt.md"
    content = read_file(prompt_path)
    if content is None:
        # Fallback minimal prompt
        return """Generate SKILL.md content for the given skill proposal.
Create the skill folder with SKILL.md and any reference files."""
    return content


def _build_scaffold_prompt(proposal: dict[str, Any], skill_path: Path) -> str:
    """Build the full prompt for skill scaffolding.

    Args:
        proposal: Skill proposal to scaffold.
        skill_path: Path where skill folder should be created.

    Returns:
        Complete prompt string.
    """
    template = _load_prompt_template()
    now = datetime.now(UTC).isoformat()

    parts = [
        template,
        "",
        "---",
        "",
        "## Skill Proposal",
        "",
        "```json",
        json.dumps(proposal, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Output Location",
        "",
        f"Create the skill at: `{skill_path}`",
        "",
        "Write the following files:",
        f"- `{skill_path}/SKILL.md` - Main skill file with YAML frontmatter",
        "- Any reference files mentioned in `suggested_references`",
        "",
        "## Metadata",
        "",
        f"- Current timestamp: {now}",
        "",
        "## Instructions",
        "",
        "Use the Write tool to create each file.",
        "Do NOT return JSON - write files directly.",
    ]

    return "\n".join(parts)


def _generate_simple_skill_md(proposal: dict[str, Any]) -> str:
    """Generate a simple SKILL.md without LLM.

    Used as fallback when LLM is skipped or fails.

    Args:
        proposal: Skill proposal.

    Returns:
        SKILL.md content.
    """
    name = proposal.get("name", "unknown")
    description = proposal.get("description", "")
    triggers = proposal.get("triggers", [])
    tools = proposal.get("allowed_tools", ["Read", "Grep", "Glob"])
    rationale = proposal.get("rationale", "")

    # Build trigger list for description
    trigger_lines = "\n".join(f'  - "{t}"' for t in triggers)

    # Build tools list
    tools_lines = "\n".join(f"  - {t}" for t in tools)

    return f"""---
name: {name}
description: |
  {description}
  Use when you hear:
{trigger_lines}
allowed-tools:
{tools_lines}
---

# {name.replace("-", " ").title()}

{description}

## When to Use

{rationale}

## Workflow

1. Analyze the request
2. Gather relevant context
3. Execute the task
4. Verify the result

## Examples

### Basic Usage

User: "{triggers[0] if triggers else "help me with this"}"

The skill will analyze the context and provide appropriate assistance.
"""


@app.callback(invoke_without_command=True)
def main(
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
    """Scaffold a new skill from a proposal.

    Takes a skill proposal (from propose_skills.py output) and generates
    the skill folder with SKILL.md and reference files.
    """
    # Recursion guard
    if is_internal_call():
        _logger.debug("Skipping scaffold skill (internal call)")
        raise typer.Exit(0)

    _logger.info("Starting skill scaffolding")

    # Load proposals file
    state_dir = get_voyager_state_dir()
    proposals_path = proposal_json or (state_dir / "skill_proposals.json")

    if not proposals_path.exists():
        typer.echo(f"Error: Proposals file not found: {proposals_path}", err=True)
        typer.echo("Run propose_skills.py first to generate proposals.", err=True)
        raise typer.Exit(1)

    proposals_data = read_json(proposals_path)
    if not proposals_data or not proposals_data.get("proposals"):
        typer.echo("Error: No proposals found in file", err=True)
        raise typer.Exit(1)

    proposals = proposals_data["proposals"]

    # Find the target proposal
    proposal: dict[str, Any] | None = None

    if proposal_name:
        # Find by name
        for p in proposals:
            if p.get("name") == proposal_name:
                proposal = p
                break
        if not proposal:
            typer.echo(f"Error: Proposal '{proposal_name}' not found", err=True)
            typer.echo("Available proposals:", err=True)
            for p in proposals:
                typer.echo(f"  - {p.get('name')}", err=True)
            raise typer.Exit(1)
    else:
        # Use index
        if proposal_index >= len(proposals):
            typer.echo(
                f"Error: Index {proposal_index} out of range (0-{len(proposals) - 1})",
                err=True,
            )
            raise typer.Exit(1)
        proposal = proposals[proposal_index]

    skill_name = proposal.get("name", "")
    if not skill_name:
        typer.echo("Error: Proposal has no name", err=True)
        raise typer.Exit(1)

    _logger.info("Scaffolding skill: %s", skill_name)

    # Check if skill already exists
    if skill_exists(skill_name) and not force:
        typer.echo(f"Error: Skill '{skill_name}' already exists", err=True)
        typer.echo("Use --force to overwrite", err=True)
        raise typer.Exit(1)

    skill_path = get_skill_folder_path(skill_name)

    # Generate scaffold
    if skip_llm or dry_run:
        skill_md = _generate_simple_skill_md(proposal)
        if dry_run:
            typer.echo("=== SKILL.md ===")
            typer.echo(skill_md)
            raise typer.Exit(0)

        # Write manually when skipping LLM
        skill_path.mkdir(parents=True, exist_ok=True)
        skill_md_path = skill_path / "SKILL.md"
        if not write_file(skill_md_path, skill_md):
            _logger.error("Failed to write SKILL.md")
            save_last_update(
                "scaffold",
                "failed",
                skill_name=skill_name,
                error="Failed to write SKILL.md",
            )
            typer.echo("Error: Failed to write SKILL.md", err=True)
            raise typer.Exit(1)

        files_created = [str(skill_md_path)]
        _logger.info("Using simple template (LLM skipped)")
    else:
        # Build prompt and call LLM agent
        prompt = _build_scaffold_prompt(proposal, skill_path)

        _logger.info("Calling LLM agent to generate skill content...")
        result = call_claude(
            prompt,
            cwd=skill_path.parent,
            timeout_seconds=120,
        )

        if result.success and result.files:
            files_created = result.files
            _logger.info("LLM scaffold generation successful")
        else:
            # LLM failed, use fallback
            _logger.warning("LLM call failed: %s, using fallback", result.error)
            skill_md = _generate_simple_skill_md(proposal)
            skill_path.mkdir(parents=True, exist_ok=True)
            skill_md_path = skill_path / "SKILL.md"
            if not write_file(skill_md_path, skill_md):
                save_last_update(
                    "scaffold",
                    "failed",
                    skill_name=skill_name,
                    error="Failed to write SKILL.md",
                )
                typer.echo("Error: Failed to write SKILL.md", err=True)
                raise typer.Exit(1)
            files_created = [str(skill_md_path)]

    # Add to index
    if add_skill_to_index(skill_name, skill_path, proposal):
        _logger.info("Added %s to skills index", skill_name)
    else:
        _logger.warning("Failed to add %s to skills index", skill_name)

    # Save last update
    save_last_update("scaffold", "success", skill_name=skill_name)

    typer.echo(f"Scaffolded skill: {skill_path}", err=True)
    for file_path in files_created:
        typer.echo(f"  - {Path(file_path).name} created", err=True)


@app.command("list")
def list_proposals(
    proposal_json: Annotated[
        Path | None,
        typer.Option("--proposal", "-p", help="Path to proposals JSON file"),
    ] = None,
) -> None:
    """List available skill proposals."""
    state_dir = get_voyager_state_dir()
    proposals_path = proposal_json or (state_dir / "skill_proposals.json")

    if not proposals_path.exists():
        typer.echo(f"No proposals file found: {proposals_path}", err=True)
        typer.echo("Run propose_skills.py first to generate proposals.", err=True)
        raise typer.Exit(1)

    proposals_data = read_json(proposals_path)
    if not proposals_data or not proposals_data.get("proposals"):
        typer.echo("No proposals found", err=True)
        raise typer.Exit(0)

    proposals = proposals_data["proposals"]
    typer.echo(f"Found {len(proposals)} proposals:\n")

    for i, p in enumerate(proposals):
        name = p.get("name", "unknown")
        desc = p.get("description", "")
        priority = p.get("priority", "medium")
        complexity = p.get("complexity", "moderate")
        triggers = p.get("triggers", [])

        typer.echo(f"[{i}] {name}")
        typer.echo(f"    {desc}")
        typer.echo(f"    Priority: {priority} | Complexity: {complexity}")
        if triggers:
            typer.echo(f"    Triggers: {', '.join(triggers[:3])}")
        typer.echo()


if __name__ == "__main__":
    app()
