"""Curriculum store for Voyager.

Provides load/save operations for curriculum.json with validation
and last-update tracking.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voyager.config import (
    get_curriculum_json_path,
    get_plugin_root,
    get_voyager_state_dir,
)
from voyager.io import read_json, write_json
from voyager.jsonschema import validate
from voyager.logging import get_logger

_logger = get_logger("curriculum.store")

# Path to the curriculum schema relative to plugin root
CURRICULUM_SCHEMA_REL_PATH = "skills/curriculum-planner/schemas/curriculum.schema.json"


def get_curriculum_schema_path() -> Path:
    """Get the path to the curriculum JSON schema."""
    return get_plugin_root() / CURRICULUM_SCHEMA_REL_PATH


def create_empty_curriculum() -> dict[str, Any]:
    """Create an empty curriculum structure with default values.

    Returns:
        Valid empty curriculum dict conforming to schema.
    """
    now = datetime.now(UTC).isoformat()
    return {
        "version": 1,
        "goal": "",
        "tracks": [],
        "metadata": {
            "created_at": now,
            "updated_at": now,
            "total_tasks": 0,
        },
    }


def load_curriculum(path: Path | str | None = None) -> dict[str, Any]:
    """Load curriculum.json, returning empty curriculum if missing or invalid.

    Args:
        path: Path to curriculum.json. Defaults to project curriculum path.

    Returns:
        Curriculum dict, either loaded from file or empty default.
    """
    if path is None:
        path = get_curriculum_json_path()
    path = Path(path)

    data = read_json(path)
    if data is None:
        _logger.info("No curriculum.json found at %s, starting fresh", path)
        return create_empty_curriculum()

    # Validate against schema
    schema_path = get_curriculum_schema_path()
    is_valid, errors = validate(data, schema_path)

    if not is_valid:
        _logger.warning("curriculum.json failed validation: %s. Starting fresh.", errors)
        # Back up invalid curriculum for debugging
        backup_path = path.with_suffix(".json.bak")
        write_json(backup_path, data)
        _logger.info("Backed up invalid curriculum to %s", backup_path)
        return create_empty_curriculum()

    return data


def save_curriculum(
    curriculum: dict[str, Any],
    path: Path | str | None = None,
    *,
    validate_schema: bool = True,
) -> bool:
    """Save curriculum.json with optional validation.

    Args:
        curriculum: Curriculum dict to save.
        path: Path to curriculum.json. Defaults to project curriculum path.
        validate_schema: Whether to validate before saving.

    Returns:
        True if save succeeded, False otherwise.
    """
    if path is None:
        path = get_curriculum_json_path()
    path = Path(path)

    if validate_schema:
        schema_path = get_curriculum_schema_path()
        is_valid, errors = validate(curriculum, schema_path)
        if not is_valid:
            _logger.error("Curriculum validation failed, not saving: %s", errors)
            return False

    success = write_json(path, curriculum)
    if success:
        _logger.debug("Saved curriculum to %s", path)
    else:
        _logger.error("Failed to save curriculum to %s", path)
    return success


def save_last_update(
    status: str,
    *,
    error: str | None = None,
    brain_session: str | None = None,
    task_count: int = 0,
) -> bool:
    """Save last update metadata for debugging.

    Creates `.claude/voyager/curriculum.last_update.json` with info about
    the most recent curriculum planning attempt.

    Args:
        status: Update status (e.g., "success", "failed", "skipped").
        error: Error message if failed.
        brain_session: Session ID from brain used as input.
        task_count: Number of tasks generated.

    Returns:
        True if save succeeded.
    """
    state_dir = get_voyager_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    last_update_path = state_dir / "curriculum.last_update.json"
    data: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "status": status,
        "task_count": task_count,
    }
    if error:
        data["error"] = error
    if brain_session:
        data["brain_session"] = brain_session

    return write_json(last_update_path, data)
