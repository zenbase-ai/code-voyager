"""Tests for voyager.logging module."""

from __future__ import annotations

import logging
import os
from unittest import mock

import pytest


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger(self) -> None:
        """Should return a logging.Logger instance."""
        # Import fresh to avoid cache issues
        from voyager.logging import get_logger

        logger = get_logger("test_module")

        assert isinstance(logger, logging.Logger)
        assert "voyager.test_module" in logger.name

    def test_logs_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should output logs to stderr, not stdout."""
        from voyager.logging import get_logger

        logger = get_logger("stderr_test")
        logger.setLevel(logging.DEBUG)
        logger.warning("test message")

        captured = capsys.readouterr()
        assert "test message" in captured.err
        assert captured.out == ""

    def test_log_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should use expected log format."""
        from voyager.logging import get_logger

        logger = get_logger("format_test")
        logger.setLevel(logging.DEBUG)
        logger.warning("formatted message")

        captured = capsys.readouterr()
        assert "[voyager:format_test]" in captured.err
        assert "WARNING" in captured.err
        assert "formatted message" in captured.err

    def test_respects_env_var_level(self) -> None:
        """Should respect VOYAGER_LOG_LEVEL env var."""
        # Clear the logger cache to force re-creation
        import voyager.logging

        voyager.logging._loggers.clear()

        with mock.patch.dict(os.environ, {"VOYAGER_LOG_LEVEL": "DEBUG"}):
            logger = voyager.logging.get_logger("env_test")
            assert logger.level == logging.DEBUG

    def test_default_level_warning(self) -> None:
        """Should default to WARNING level."""
        import voyager.logging

        voyager.logging._loggers.clear()

        # Ensure env var is not set
        with mock.patch.dict(os.environ, {}, clear=True):
            # Remove the specific var if it exists
            os.environ.pop("VOYAGER_LOG_LEVEL", None)
            logger = voyager.logging.get_logger("default_level_test")
            assert logger.level == logging.WARNING

    def test_caches_loggers(self) -> None:
        """Should return same logger instance for same name."""
        from voyager.logging import get_logger

        logger1 = get_logger("cache_test")
        logger2 = get_logger("cache_test")

        assert logger1 is logger2

    def test_different_names_different_loggers(self) -> None:
        """Should return different loggers for different names."""
        from voyager.logging import get_logger

        logger1 = get_logger("name_a")
        logger2 = get_logger("name_b")

        assert logger1 is not logger2
        assert logger1.name != logger2.name
