"""Tests for voyager.jsonschema module."""

from __future__ import annotations

from pathlib import Path

from voyager.jsonschema import validate, validate_hook_context


class TestValidate:
    """Tests for validate function."""

    def test_valid_data_passes(self) -> None:
        """Should return (True, []) for valid data."""
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        data = {"name": "Alice", "age": 30}

        valid, errors = validate(data, schema)

        assert valid is True
        assert errors == []

    def test_missing_required_field(self) -> None:
        """Should report missing required fields."""
        schema = {
            "type": "object",
            "required": ["name", "email"],
        }
        data = {"name": "Alice"}

        valid, errors = validate(data, schema)

        assert valid is False
        assert any("email" in err for err in errors)

    def test_wrong_type(self) -> None:
        """Should report type mismatches."""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
        }
        data = {"count": "not a number"}

        valid, errors = validate(data, schema)

        assert valid is False
        assert any("integer" in err for err in errors)

    def test_array_validation(self) -> None:
        """Should validate array items."""
        schema = {
            "type": "array",
            "items": {"type": "string"},
        }
        data = ["a", "b", 123]

        valid, errors = validate(data, schema)

        assert valid is False
        assert any("[2]" in err for err in errors)

    def test_loads_schema_from_file(self, tmp_path: Path) -> None:
        """Should load schema from file path."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(
            '{"type": "object", "required": ["id"]}',
            encoding="utf-8",
        )

        valid, errors = validate({"id": 1}, schema_file)
        assert valid is True

        valid, errors = validate({}, schema_file)
        assert valid is False

    def test_missing_schema_file(self, tmp_path: Path) -> None:
        """Should handle missing schema file gracefully."""
        schema_file = tmp_path / "nonexistent.json"

        valid, errors = validate({"data": 1}, schema_file)

        assert valid is False
        assert any("Could not load schema" in err for err in errors)

    def test_never_raises(self) -> None:
        """Should never raise exceptions."""
        # Pass invalid schema type
        valid, errors = validate({"data": 1}, "not a dict or path")

        # Should not raise, just return False
        assert valid is False

    def test_type_number_accepts_int_and_float(self) -> None:
        """Type 'number' should accept both int and float."""
        schema = {"type": "number"}

        valid, _ = validate(42, schema)
        assert valid is True

        valid, _ = validate(3.14, schema)
        assert valid is True

    def test_type_integer_rejects_float(self) -> None:
        """Type 'integer' should reject floats."""
        schema = {"type": "integer"}

        valid, _ = validate(42, schema)
        assert valid is True

        valid, _ = validate(3.14, schema)
        assert valid is False

    def test_boolean_not_number(self) -> None:
        """Booleans should not be accepted as numbers."""
        schema = {"type": "number"}

        valid, _ = validate(True, schema)
        assert valid is False


class TestValidateHookContext:
    """Tests for validate_hook_context function."""

    def test_valid_context(self) -> None:
        """Should accept valid hook context."""
        context = {
            "hook_event_name": "SessionStart",
            "session_id": "test-123",
            "cwd": "/path/to/project",
        }

        valid, errors = validate_hook_context(context)

        assert valid is True
        assert errors == []

    def test_missing_session_id(self) -> None:
        """Should require session_id."""
        context = {
            "hook_event_name": "SessionStart",
            "cwd": "/path/to/project",
        }

        valid, errors = validate_hook_context(context)

        assert valid is False
        assert any("session_id" in err for err in errors)

    def test_wrong_event_name(self) -> None:
        """Should check event name when specified."""
        context = {
            "hook_event_name": "SessionEnd",
            "session_id": "test-123",
        }

        valid, errors = validate_hook_context(context, event_name="SessionStart")

        assert valid is False
        assert any("SessionStart" in err for err in errors)

    def test_correct_event_name(self) -> None:
        """Should pass when event name matches."""
        context = {
            "hook_event_name": "SessionStart",
            "session_id": "test-123",
        }

        valid, errors = validate_hook_context(context, event_name="SessionStart")

        assert valid is True

    def test_non_object_context(self) -> None:
        """Should reject non-object contexts."""
        valid, errors = validate_hook_context("not an object")

        assert valid is False
        assert any("object" in err.lower() for err in errors)

    def test_extra_fields_allowed(self) -> None:
        """Should allow extra fields (lenient validation)."""
        context = {
            "hook_event_name": "SessionStart",
            "session_id": "test-123",
            "extra_field": "allowed",
            "another": 123,
        }

        valid, errors = validate_hook_context(context)

        assert valid is True
