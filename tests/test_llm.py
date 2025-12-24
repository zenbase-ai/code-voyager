"""Tests for voyager.llm module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from voyager.llm import (
    RECURSION_GUARD_VAR,
    LLMResult,
    call_claude,
    is_internal_call,
)


class TestIsInternalCall:
    """Tests for is_internal_call function."""

    def test_returns_true_when_guard_set(self) -> None:
        """Should return True when recursion guard is set."""
        with patch.dict(os.environ, {RECURSION_GUARD_VAR: "1"}):
            assert is_internal_call() is True

    def test_returns_false_when_guard_not_set(self) -> None:
        """Should return False when recursion guard is not set."""
        env = os.environ.copy()
        env.pop(RECURSION_GUARD_VAR, None)
        with patch.dict(os.environ, env, clear=True):
            assert is_internal_call() is False

    def test_returns_false_when_guard_not_one(self) -> None:
        """Should return False when guard is set to something other than '1'."""
        with patch.dict(os.environ, {RECURSION_GUARD_VAR: "0"}):
            assert is_internal_call() is False
        with patch.dict(os.environ, {RECURSION_GUARD_VAR: "true"}):
            assert is_internal_call() is False


class TestLLMResult:
    """Tests for LLMResult dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        result = LLMResult(success=True)

        assert result.output == ""
        assert result.files == []
        assert result.error == ""

    def test_files_not_shared(self) -> None:
        """Should not share files list between instances."""
        result1 = LLMResult(success=True)
        result2 = LLMResult(success=True)

        result1.files.append("/path/to/file")

        assert "/path/to/file" not in result2.files


class TestCallClaude:
    """Tests for call_claude function."""

    def test_sets_recursion_guard(self) -> None:
        """Should set recursion guard environment variable when calling."""
        captured_env = []

        async def mock_query(*args, **kwargs):
            captured_env.append(os.environ.get(RECURSION_GUARD_VAR))
            # Return empty to end iteration
            return
            yield  # Make this a generator

        with patch("voyager.llm.query", mock_query):
            call_claude("test prompt")

        assert "1" in captured_env

    def test_restores_recursion_guard(self) -> None:
        """Should restore recursion guard after call."""
        original = os.environ.get(RECURSION_GUARD_VAR)

        async def mock_query(*args, **kwargs):
            return
            yield

        with patch("voyager.llm.query", mock_query):
            call_claude("test prompt")

        assert os.environ.get(RECURSION_GUARD_VAR) == original

    def test_handles_timeout(self) -> None:
        """Should handle timeout gracefully."""

        async def slow_query(*args, **kwargs):
            import anyio

            await anyio.sleep(100)
            yield

        with patch("voyager.llm.query", slow_query):
            result = call_claude("test prompt", timeout_seconds=1)

        assert result.success is False
        assert "timed out" in result.error

    def test_handles_exception(self) -> None:
        """Should handle exceptions gracefully."""

        async def failing_query(*args, **kwargs):
            raise RuntimeError("Test error")
            yield

        with patch("voyager.llm.query", failing_query):
            result = call_claude("test prompt")

        assert result.success is False
        assert "Test error" in result.error

    def test_returns_output_and_files(self) -> None:
        """Should return output and files from successful call."""
        from claude_agent_sdk.types import (
            AssistantMessage,
            ResultMessage,
            ToolUseBlock,
        )

        # Create mock messages
        write_block = MagicMock(spec=ToolUseBlock)
        write_block.name = "Write"
        write_block.input = {"file_path": "/tmp/test.txt"}

        assistant_msg = MagicMock(spec=AssistantMessage)
        assistant_msg.content = [write_block]

        result_msg = MagicMock(spec=ResultMessage)
        result_msg.result = "Done!"

        async def mock_query(*args, **kwargs):
            yield assistant_msg
            yield result_msg

        with patch("voyager.llm.query", mock_query):
            result = call_claude("test prompt")

        assert result.success is True
        assert result.output == "Done!"
        assert "/tmp/test.txt" in result.files
