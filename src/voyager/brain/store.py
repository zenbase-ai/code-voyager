"""Brain store for Session Brain state.

Provides load/save operations for brain.json with validation,
episode management, and last-update tracking.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voyager.config import (
    get_brain_json_path,
    get_episodes_dir,
    get_plugin_root,
    get_voyager_state_dir,
)
from voyager.io import read_json, write_file, write_json
from voyager.jsonschema import validate
from voyager.logging import get_logger

_logger = get_logger("brain.store")

# Path to the brain schema relative to plugin root
BRAIN_SCHEMA_REL_PATH = "skills/session-brain/schemas/brain.schema.json"


def get_brain_schema_path() -> Path:
    """Get the path to the brain JSON schema."""
    return get_plugin_root() / BRAIN_SCHEMA_REL_PATH


def create_empty_brain(session_id: str = "") -> dict[str, Any]:
    """Create an empty brain structure with default values.

    Args:
        session_id: Optional session ID to record.

    Returns:
        Valid empty brain dict conforming to schema.
    """
    now = datetime.now(UTC).isoformat()
    return {
        "version": 1,
        "project": {
            "summary": "",
            "stack_guesses": [],
            "key_commands": [],
        },
        "working_set": {
            "current_goal": "",
            "current_plan": [],
            "open_questions": [],
            "risks": [],
        },
        "decisions": [],
        "progress": {
            "recent_changes": [],
            "done": [],
        },
        "signals": {
            "last_session_id": session_id,
            "last_updated_at": now,
        },
    }


def load_brain(path: Path | str | None = None) -> dict[str, Any]:
    """Load brain.json, returning empty brain if missing or invalid.

    Args:
        path: Path to brain.json. Defaults to project brain path.

    Returns:
        Brain dict, either loaded from file or empty default.
    """
    if path is None:
        path = get_brain_json_path()
    path = Path(path)

    data = read_json(path)
    if data is None:
        _logger.info("No brain.json found at %s, starting fresh", path)
        return create_empty_brain()

    # Validate against schema
    schema_path = get_brain_schema_path()
    is_valid, errors = validate(data, schema_path)

    if not is_valid:
        _logger.warning("brain.json failed validation: %s. Starting fresh.", errors)
        # Back up invalid brain for debugging
        backup_path = path.with_suffix(".json.bak")
        write_json(backup_path, data)
        _logger.info("Backed up invalid brain to %s", backup_path)
        return create_empty_brain()

    return data


def save_brain(
    brain: dict[str, Any],
    path: Path | str | None = None,
    *,
    validate_schema: bool = True,
) -> bool:
    """Save brain.json with optional validation.

    Args:
        brain: Brain dict to save.
        path: Path to brain.json. Defaults to project brain path.
        validate_schema: Whether to validate before saving.

    Returns:
        True if save succeeded, False otherwise.
    """
    if path is None:
        path = get_brain_json_path()
    path = Path(path)

    if validate_schema:
        schema_path = get_brain_schema_path()
        is_valid, errors = validate(brain, schema_path)
        if not is_valid:
            _logger.error("Brain validation failed, not saving: %s", errors)
            return False

    success = write_json(path, brain)
    if success:
        _logger.debug("Saved brain to %s", path)
    else:
        _logger.error("Failed to save brain to %s", path)
    return success


def save_episode(
    brain: dict[str, Any],
    session_id: str,
    *,
    include_md: bool = True,
) -> Path | None:
    """Save an episode snapshot for this session.

    Episodes are stored as `<timestamp>_<session_id>.json` in the episodes dir.

    Args:
        brain: Brain dict to snapshot.
        session_id: Session identifier.
        include_md: Also save a .md file alongside JSON.

    Returns:
        Path to the saved episode file, or None on failure.
    """
    episodes_dir = get_episodes_dir()
    episodes_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    # Sanitize session_id for filename
    safe_session_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)[:32]

    filename = f"{timestamp}_{safe_session_id}"
    json_path = episodes_dir / f"{filename}.json"

    if not write_json(json_path, brain):
        _logger.error("Failed to write episode to %s", json_path)
        return None

    _logger.debug("Saved episode to %s", json_path)

    if include_md:
        from voyager.brain.render import render_brain_md

        md_content = render_brain_md(brain)
        md_path = episodes_dir / f"{filename}.md"
        if write_file(md_path, md_content):
            _logger.debug("Saved episode MD to %s", md_path)
        else:
            _logger.warning("Failed to write episode MD to %s", md_path)

    return json_path


def save_last_update(
    session_id: str,
    status: str,
    *,
    error: str | None = None,
    transcript_lines: int = 0,
) -> bool:
    """Save last update metadata for debugging.

    Creates `.claude/voyager/brain.last_update.json` with info about
    the most recent brain update attempt.

    Args:
        session_id: Session identifier.
        status: Update status (e.g., "success", "failed", "skipped").
        error: Error message if failed.
        transcript_lines: Number of transcript lines processed.

    Returns:
        True if save succeeded.
    """
    state_dir = get_voyager_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    last_update_path = state_dir / "brain.last_update.json"
    data: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "status": status,
        "transcript_lines": transcript_lines,
    }
    if error:
        data["error"] = error

    return write_json(last_update_path, data)
