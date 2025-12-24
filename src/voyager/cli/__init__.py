"""Unified CLI for Voyager.

Provides a single entry point with subcommands organized by domain:

    voyager brain update ...      # Update session brain
    voyager brain inject ...      # Inject brain context
    voyager curriculum plan ...   # Generate curriculum
    voyager repo snapshot ...     # Generate repo snapshot
    voyager factory propose ...   # Propose new skills
    voyager factory scaffold ...  # Scaffold a skill
    voyager factory list          # List skill proposals
    voyager skill index ...       # Build skill search index
    voyager skill find ...        # Search for skills
    voyager feedback insights ... # Analyze feedback
    voyager hook session-start    # Claude Code SessionStart hook
    voyager hook session-end      # Claude Code SessionEnd hook
    voyager hook pre-compact      # Claude Code PreCompact hook
    voyager hook post-tool-use    # Claude Code PostToolUse hook
"""

import typer

from voyager.cli import brain, curriculum, factory, feedback, hook, repo, skill

app = typer.Typer(
    name="voyager",
    help="Voyager: Meta-skills for Coding Agents",
    no_args_is_help=True,
)

app.add_typer(brain.app)
app.add_typer(curriculum.app)
app.add_typer(feedback.app)
app.add_typer(factory.app)
app.add_typer(hook.app)
app.add_typer(repo.app)
app.add_typer(skill.app)


def main() -> None:
    """Main entry point for the voyager CLI."""
    app()


if __name__ == "__main__":
    main()
