"""Skill insights CLI.

Analyzes feedback data and generates actionable improvement suggestions.

Run: voyager feedback insights
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from voyager.config import get_feedback_db_path
from voyager.logging import get_logger

_logger = get_logger("feedback.insights")


def format_success_rate(rate: float) -> str:
    """Format success rate with color-like indicator."""
    pct = rate * 100
    if pct >= 90 or pct >= 70:
        return f"{pct:.1f}%"
    else:
        return f"{pct:.1f}%"


def generate_skill_recommendations(
    store: Any,
    skill_id: str,
    stats: dict[str, Any],
) -> list[str]:
    """Generate improvement recommendations for a skill.

    Args:
        store: FeedbackStore instance.
        skill_id: Skill identifier.
        stats: Skill statistics.

    Returns:
        List of recommendation strings.
    """
    recommendations: list[str] = []

    # Check success rate
    success_rate = stats.get("success_rate", 1.0)
    if success_rate < 0.7:
        recommendations.append(
            f"Low success rate ({success_rate:.0%}). Review common errors and update SKILL.md with better guidance."
        )

    # Check common errors
    errors = store.get_common_errors(skill_id, limit=3)
    if errors:
        top_error = errors[0]
        if top_error["count"] > 2:
            error_preview = top_error["error"][:60] if top_error["error"] else "unknown"
            recommendations.append(f"Recurring error ({top_error['count']}x): {error_preview}...")

    # Low usage might indicate discoverability issues
    if stats["total"] < 3:
        recommendations.append("Low usage - consider adding more trigger phrases to SKILL.md")

    return recommendations


def main(
    db_path: Path | None = None,
    skill: str | None = None,
    since: str | None = None,
    json_output: bool = False,
    errors: bool = False,
) -> None:
    """Analyze feedback and generate skill insights.

    Args:
        db_path: Path to the feedback database.
        skill: Filter insights for a specific skill.
        since: Only analyze feedback since this date (ISO format).
        json_output: Output results as JSON.
        errors: Show common errors.
    """
    if db_path is None:
        db_path = get_feedback_db_path()

    if not db_path.exists():
        typer.echo("No feedback data yet.")
        typer.echo("Run 'voyager feedback setup' to start collecting feedback.")
        raise typer.Exit(1)

    from voyager.refinement.store import FeedbackStore

    store = FeedbackStore(db_path)

    # Get total counts
    counts = store.get_total_counts()

    if counts["total_executions"] == 0:
        typer.echo("No feedback data yet.")
        typer.echo("Use Claude Code with skills, then check back!")
        raise typer.Exit(0)

    if skill:
        # Single skill analysis
        stats = store.get_skill_stats(skill)
        if skill not in stats:
            typer.echo(f"No data for skill: {skill}")
            raise typer.Exit(1)

        s = stats[skill]

        if json_output:
            output = {
                "skill": skill,
                "stats": s,
                "errors": store.get_common_errors(skill) if errors else [],
                "recommendations": generate_skill_recommendations(store, skill, s),
            }
            typer.echo(json.dumps(output, indent=2))
            return

        typer.echo(f"\nSkill: {skill}")
        typer.echo(f"  Total uses: {s['total']}")
        typer.echo(f"  Success rate: {format_success_rate(s['success_rate'])}")
        typer.echo(f"  Failed: {s['failed']}")

        if errors:
            skill_errors = store.get_common_errors(skill)
            if skill_errors:
                typer.echo("\n  Common errors:")
                for e in skill_errors[:5]:
                    preview = e["error"][:60] if e["error"] else "unknown"
                    typer.echo(f"    ({e['count']}x) {preview}...")

        recommendations = generate_skill_recommendations(store, skill, s)
        if recommendations:
            typer.echo("\n  Recommendations:")
            for rec in recommendations:
                typer.echo(f"    - {rec}")

    else:
        # Overview of all skills
        skill_stats = store.get_skill_stats()
        tool_stats = store.get_tool_usage_stats()

        if json_output:
            output: dict[str, Any] = {
                "summary": counts,
                "skills": skill_stats,
                "tools": tool_stats,
                "recommendations": [],
            }

            # Generate recommendations for each skill
            for skill_id, s in skill_stats.items():
                recs = generate_skill_recommendations(store, skill_id, s)
                if recs:
                    output["recommendations"].append(
                        {
                            "skill": skill_id,
                            "recommendations": recs,
                        }
                    )

            typer.echo(json.dumps(output, indent=2))
            return

        typer.echo("\nFeedback Insights")
        typer.echo("=" * 50)
        typer.echo(f"\nSummary: {counts['total_executions']} tool calls across {counts['total_sessions']} sessions")
        typer.echo(f"Skills detected: {counts['total_skills']}")

        # Skill performance
        if skill_stats:
            typer.echo("\nSkill Performance")
            typer.echo("-" * 50)
            typer.echo(f"{'Skill':<25} {'Uses':>8} {'Success':>10} {'Failed':>8}")
            typer.echo("-" * 50)

            for skill_id, s in sorted(
                skill_stats.items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            ):
                typer.echo(
                    f"{skill_id:<25} {s['total']:>8} {format_success_rate(s['success_rate']):>10} {s['failed']:>8}"
                )

        # Tool usage
        if tool_stats:
            typer.echo("\nTool Usage")
            typer.echo("-" * 50)
            typer.echo(f"{'Tool':<20} {'Uses':>8} {'Success':>10} {'Failed':>8}")
            typer.echo("-" * 50)

            for tool_name, s in sorted(
                tool_stats.items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            )[:10]:  # Top 10 tools
                typer.echo(
                    f"{tool_name:<20} {s['total']:>8} {format_success_rate(s['success_rate']):>10} {s['failed']:>8}"
                )

        # Global errors
        if errors:
            all_errors = store.get_common_errors(limit=5)
            if all_errors:
                typer.echo("\nTop Errors")
                typer.echo("-" * 50)
                for e in all_errors:
                    preview = e["error"][:50] if e["error"] else "unknown"
                    skill_info = f" ({e['skill']})" if e.get("skill") else ""
                    typer.echo(f"  ({e['count']}x) [{e['tool']}{skill_info}] {preview}...")

        # Recommendations
        all_recs: list[tuple[str, str]] = []
        for skill_id, s in skill_stats.items():
            recs = generate_skill_recommendations(store, skill_id, s)
            for rec in recs:
                all_recs.append((skill_id, rec))

        if all_recs:
            typer.echo("\nRecommendations")
            typer.echo("-" * 50)
            for skill_id, rec in all_recs[:5]:  # Top 5 recommendations
                typer.echo(f"  [{skill_id}] {rec}")

        typer.echo()


if __name__ == "__main__":
    main()
