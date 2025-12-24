"""Auto-discover skills from common locations.

No configuration required - skills are discovered from:
1. Environment variable CLAUDE_SKILLS_PATH
2. Plugin skills: ./skills/
3. Local mirror: ./.claude/skills/local/
4. Generated skills: ./.claude/skills/generated/
5. User skills: ~/.claude/skills/
"""

from __future__ import annotations

import os
from pathlib import Path

from voyager.config import (
    get_generated_skills_dir,
    get_local_skills_dir,
    get_plugin_skills_dir,
)
from voyager.logging import get_logger

_logger = get_logger("retrieval.discovery")


def discover_skills_roots(
    extra_paths: list[Path] | None = None,
) -> list[Path]:
    """Discover all skill root directories.

    Args:
        extra_paths: Additional paths to include.

    Returns:
        List of existing skill root directories.
    """
    roots: list[Path] = []

    # Check environment variable first
    env_path = os.environ.get("CLAUDE_SKILLS_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            roots.append(p)
            _logger.debug("Found skills from env: %s", p)

    # Standard locations (project-relative)
    candidates = [
        get_plugin_skills_dir(),  # ./skills/
        get_local_skills_dir(),  # ./.claude/skills/local/
        get_generated_skills_dir(),  # ./.claude/skills/generated/
    ]

    # User-global skills
    user_skills = Path.home() / ".claude" / "skills"
    candidates.append(user_skills)

    # Add extra paths
    if extra_paths:
        candidates.extend(extra_paths)

    for candidate in candidates:
        if candidate.exists() and candidate not in roots and any(candidate.rglob("SKILL.md")):
            roots.append(candidate)
            _logger.debug("Found skills root: %s", candidate)

    return roots


def discover_all_skills(
    roots: list[Path] | None = None,
    extra_paths: list[Path] | None = None,
) -> list[Path]:
    """Find all skill directories containing SKILL.md.

    Args:
        roots: Specific root directories to search. If None, auto-discover.
        extra_paths: Additional paths to include when auto-discovering.

    Returns:
        List of paths to skill directories (parent of SKILL.md).
    """
    if roots is None:
        roots = discover_skills_roots(extra_paths=extra_paths)

    if not roots:
        _logger.warning("No skill roots found")
        return []

    skills: list[Path] = []
    seen: set[Path] = set()

    for root in roots:
        _logger.debug("Scanning %s for skills...", root)
        for skill_md in root.rglob("SKILL.md"):
            skill_dir = skill_md.parent.resolve()
            if skill_dir not in seen:
                seen.add(skill_dir)
                skills.append(skill_dir)
                _logger.debug("Found skill: %s", skill_dir.name)

    _logger.info("Discovered %d skills from %d roots", len(skills), len(roots))
    return skills
