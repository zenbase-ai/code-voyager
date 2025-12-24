"""Factory store for Voyager skill generation.

Provides load/save operations for the generated skills index
and skill proposals with validation and tracking.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voyager.config import (
    get_generated_skills_dir,
    get_generated_skills_index_path,
    get_plugin_root,
    get_voyager_state_dir,
)
from voyager.io import read_json, write_json
from voyager.jsonschema import validate
from voyager.logging import get_logger

_logger = get_logger("factory.store")

# Path to the skill proposal schema relative to plugin root
SKILL_PROPOSAL_SCHEMA_REL_PATH = "skills/skill-factory/schemas/skill_proposal.schema.json"


def get_skill_proposal_schema_path() -> Path:
    """Get the path to the skill proposal JSON schema."""
    return get_plugin_root() / SKILL_PROPOSAL_SCHEMA_REL_PATH


def create_empty_index() -> dict[str, Any]:
    """Create an empty generated skills index.

    Returns:
        Valid empty index dict.
    """
    now = datetime.now(UTC).isoformat()
    return {
        "version": 1,
        "skills": [],
        "metadata": {
            "created_at": now,
            "updated_at": now,
            "total_skills": 0,
        },
    }


def load_skills_index(path: Path | str | None = None) -> dict[str, Any]:
    """Load the generated skills index, returning empty if missing.

    Args:
        path: Path to index JSON. Defaults to project index path.

    Returns:
        Index dict, either loaded from file or empty default.
    """
    if path is None:
        path = get_generated_skills_index_path()
    path = Path(path)

    data = read_json(path)
    if data is None:
        _logger.info("No generated skills index found at %s, starting fresh", path)
        return create_empty_index()

    return data


def save_skills_index(
    index: dict[str, Any],
    path: Path | str | None = None,
) -> bool:
    """Save the generated skills index.

    Args:
        index: Index dict to save.
        path: Path to index JSON. Defaults to project index path.

    Returns:
        True if save succeeded, False otherwise.
    """
    if path is None:
        path = get_generated_skills_index_path()
    path = Path(path)

    # Update metadata
    index.setdefault("metadata", {})
    index["metadata"]["updated_at"] = datetime.now(UTC).isoformat()
    index["metadata"]["total_skills"] = len(index.get("skills", []))

    success = write_json(path, index)
    if success:
        _logger.debug("Saved skills index to %s", path)
    else:
        _logger.error("Failed to save skills index to %s", path)
    return success


def add_skill_to_index(
    skill_name: str,
    skill_path: Path | str,
    proposal: dict[str, Any] | None = None,
) -> bool:
    """Add a scaffolded skill to the index.

    Args:
        skill_name: Name of the skill.
        skill_path: Path to the skill folder.
        proposal: Original proposal that led to this skill.

    Returns:
        True if successful.
    """
    index = load_skills_index()
    now = datetime.now(UTC).isoformat()

    # Check for duplicates
    existing_names = {s["name"] for s in index.get("skills", [])}
    if skill_name in existing_names:
        _logger.warning("Skill %s already exists in index", skill_name)
        return False

    skill_entry = {
        "name": skill_name,
        "path": str(skill_path),
        "created_at": now,
        "status": "active",
    }
    if proposal:
        skill_entry["source_proposal"] = {
            "description": proposal.get("description", ""),
            "triggers": proposal.get("triggers", []),
            "rationale": proposal.get("rationale", ""),
        }

    index.setdefault("skills", []).append(skill_entry)
    return save_skills_index(index)


def get_existing_skill_names() -> set[str]:
    """Get names of all existing generated skills.

    Returns:
        Set of skill names.
    """
    index = load_skills_index()
    return {s["name"] for s in index.get("skills", [])}


def validate_proposals(proposals: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate skill proposals against schema.

    Args:
        proposals: Proposals dict to validate.

    Returns:
        Tuple of (is_valid, list of error messages).
    """
    schema_path = get_skill_proposal_schema_path()
    return validate(proposals, schema_path)


def save_last_update(
    operation: str,
    status: str,
    *,
    error: str | None = None,
    skill_name: str | None = None,
    proposal_count: int = 0,
) -> bool:
    """Save last update metadata for debugging.

    Creates `.claude/voyager/factory.last_update.json` with info about
    the most recent factory operation.

    Args:
        operation: Operation type (e.g., "propose", "scaffold").
        status: Update status (e.g., "success", "failed", "skipped").
        error: Error message if failed.
        skill_name: Name of skill if scaffolding.
        proposal_count: Number of proposals generated.

    Returns:
        True if save succeeded.
    """
    state_dir = get_voyager_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    last_update_path = state_dir / "factory.last_update.json"
    data: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "operation": operation,
        "status": status,
    }
    if error:
        data["error"] = error
    if skill_name:
        data["skill_name"] = skill_name
    if proposal_count:
        data["proposal_count"] = proposal_count

    return write_json(last_update_path, data)


def get_skill_folder_path(skill_name: str) -> Path:
    """Get the path where a generated skill should be scaffolded.

    Args:
        skill_name: Name of the skill.

    Returns:
        Path to the skill folder.
    """
    return get_generated_skills_dir() / skill_name


def skill_exists(skill_name: str) -> bool:
    """Check if a skill already exists.

    Args:
        skill_name: Name of the skill to check.

    Returns:
        True if skill folder exists.
    """
    skill_path = get_skill_folder_path(skill_name)
    return skill_path.exists() and (skill_path / "SKILL.md").exists()
