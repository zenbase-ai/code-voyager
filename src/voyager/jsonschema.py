"""JSON Schema validation for Voyager using the jsonschema library.

Provides schema validation with a safe API that never raises exceptions
in normal operation - returns validation results instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from voyager.io import read_json
from voyager.logging import get_logger

_logger = get_logger("jsonschema")


def validate(data: Any, schema: dict[str, Any] | Path | str) -> tuple[bool, list[str]]:
    """Validate data against a JSON Schema.

    Args:
        data: The data to validate.
        schema: Schema dict, or path to a JSON schema file.

    Returns:
        Tuple of (is_valid, list of error messages).
        Never raises - returns (False, [error]) on any failure.
    """
    try:
        # Load schema if it's a path
        if isinstance(schema, (Path, str)):
            loaded = read_json(schema)
            if loaded is None:
                return False, [f"Could not load schema from {schema}"]
            schema = loaded

        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(data))

        if errors:
            messages = [_format_error(e) for e in errors]
            for msg in messages:
                _logger.warning("Validation error: %s", msg)
            return False, messages

        return True, []

    except Exception as e:
        # Never crash hooks
        msg = f"Validation failed unexpectedly: {e}"
        _logger.warning(msg)
        return False, [msg]


def _format_error(error: ValidationError) -> str:
    """Format a validation error as a readable string."""
    parts = []
    for p in error.absolute_path:
        if isinstance(p, int):
            parts.append(f"[{p}]")
        elif parts:
            parts.append(f".{p}")
        else:
            parts.append(str(p))
    path = "".join(parts) or "$"
    return f"{path}: {error.message}"


def validate_hook_context(
    data: Any,
    event_name: str | None = None,
) -> tuple[bool, list[str]]:
    """Validate a hook context object (best-effort).

    Checks for common hook context fields. This is lenient - unknown
    fields are allowed, and missing optional fields don't cause failures.

    Args:
        data: The hook context data.
        event_name: Expected hook_event_name (optional).

    Returns:
        Tuple of (is_valid, list of error messages).
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return False, ["Hook context must be an object"]

    # Check for expected event name if provided
    if event_name is not None:
        actual = data.get("hook_event_name")
        if actual != event_name:
            errors.append(f"Expected hook_event_name '{event_name}', got '{actual}'")

    # Check for common required fields
    if "session_id" not in data:
        errors.append("Missing session_id in hook context")

    if errors:
        for err in errors:
            _logger.warning("Hook context validation: %s", err)
        return False, errors

    return True, []
