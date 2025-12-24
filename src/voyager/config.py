"""Configuration and path helpers for Voyager.

Provides canonical paths for:
- Project state (brain, curriculum, episodes)
- Skill locations (plugin, local, generated)
- Index and feedback storage
"""

import os
from pathlib import Path


def get_project_dir() -> Path:
    """Get the Claude project directory.

    Uses CLAUDE_PROJECT_DIR if set, otherwise falls back to cwd.
    """
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.cwd()


def get_plugin_root() -> Path:
    """Get the plugin root directory.

    Uses CLAUDE_PLUGIN_ROOT if set, otherwise falls back to cwd.
    """
    env_dir = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_dir:
        return Path(env_dir)
    return Path.cwd()


def get_voyager_state_dir() -> Path:
    """Get the Voyager state directory (.claude/voyager/)."""
    return get_project_dir() / ".claude" / "voyager"


def get_brain_json_path() -> Path:
    """Get the path to brain.json."""
    return get_voyager_state_dir() / "brain.json"


def get_brain_md_path() -> Path:
    """Get the path to brain.md."""
    return get_voyager_state_dir() / "brain.md"


def get_curriculum_json_path() -> Path:
    """Get the path to curriculum.json."""
    return get_voyager_state_dir() / "curriculum.json"


def get_curriculum_md_path() -> Path:
    """Get the path to curriculum.md."""
    return get_voyager_state_dir() / "curriculum.md"


def get_episodes_dir() -> Path:
    """Get the episodes directory."""
    return get_voyager_state_dir() / "episodes"


def get_feedback_db_path() -> Path:
    """Get the path to the feedback SQLite database."""
    return get_voyager_state_dir() / "feedback.db"


def get_generated_skills_dir() -> Path:
    """Get the generated skills directory."""
    return get_project_dir() / ".claude" / "skills" / "generated"


def get_generated_skills_index_path() -> Path:
    """Get the path to the generated skills index."""
    return get_voyager_state_dir() / "generated_skills_index.json"


def get_local_skills_dir() -> Path:
    """Get the local skills mirror directory."""
    return get_project_dir() / ".claude" / "skills" / "local"


def get_plugin_skills_dir() -> Path:
    """Get the plugin skills directory."""
    return get_plugin_root() / "skills"


def get_skill_index_dir() -> Path:
    """Get the skill index directory.

    Uses VOYAGER_SKILL_INDEX_PATH if set, otherwise ~/.skill-index/
    """
    env_path = os.environ.get("VOYAGER_SKILL_INDEX_PATH")
    if env_path:
        return Path(env_path)
    return Path.home() / ".skill-index"


def ensure_voyager_dirs() -> None:
    """Ensure all Voyager directories exist."""
    dirs = [
        get_voyager_state_dir(),
        get_episodes_dir(),
        get_generated_skills_dir(),
        get_local_skills_dir(),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
