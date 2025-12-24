"""LLM agent wrapper using Claude Code SDK.

Provides a way to run Claude Code as an agent that can read/write files
directly, with proper error handling and timeout support.

Usage:
    from voyager.llm import call_claude

    result = call_claude("Create a README.md file with project info")
    if result.success:
        print(f"Created files: {result.files}")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import anyio
from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import AssistantMessage, ResultMessage, ToolUseBlock

from voyager.logging import get_logger

_logger = get_logger("llm")

# Environment variable for recursion guard
RECURSION_GUARD_VAR = "VOYAGER_FOR_CODE_INTERNAL"

# Default timeout for claude calls (60 seconds)
DEFAULT_TIMEOUT_SECONDS = 60


@dataclass
class LLMResult:
    """Result of an LLM agent call.

    Attributes:
        success: Whether the call succeeded.
        output: Claude's final text output.
        files: List of file paths that were written.
        error: Error message if the call failed.
    """

    success: bool
    output: str = ""
    files: list[str] = field(default_factory=list)
    error: str = ""


def is_internal_call() -> bool:
    """Check if we're in an internal LLM call (recursion guard is set)."""
    return os.environ.get(RECURSION_GUARD_VAR) == "1"


async def _run_agent(
    prompt: str,
    *,
    model: str | None = None,
    cwd: Path | None = None,
    system_prompt: str | None = None,
    allowed_tools: list[str] | None = None,
    max_turns: int = 10,
) -> tuple[str, list[str]]:
    """Run Claude Code agent and collect results.

    Args:
        prompt: The prompt/instructions to send to Claude.
        cwd: Working directory for the agent.
        system_prompt: Optional system prompt.
        allowed_tools: List of allowed tools. Defaults to ["Read", "Write", "Glob"].
        max_turns: Maximum number of conversation turns.

    Returns:
        Tuple of (output_text, list_of_files_written).
    """
    options = ClaudeAgentOptions(
        cwd=str(cwd) if cwd else None,
        system_prompt=system_prompt,
        allowed_tools=allowed_tools or ["Read", "Write", "Glob"],
        permission_mode="acceptEdits",
        max_turns=max_turns,
        model=model,
    )

    output = ""
    files_written: list[str] = []

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            output = message.result
        elif isinstance(message, AssistantMessage):
            # Track file writes from tool use blocks
            for block in message.content:
                if isinstance(block, ToolUseBlock) and block.name == "Write":
                    file_path = block.input.get("file_path", "")
                    if file_path:
                        files_written.append(file_path)

    return output, files_written


def call_claude(
    prompt: str,
    *,
    cwd: Path | str | None = None,
    system_prompt: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    allowed_tools: list[str] | None = None,
    max_turns: int = 10,
) -> LLMResult:
    """Run Claude Code agent with file operation permissions.

    Claude Code will execute as an agent that can read/write files directly.
    The agent is limited to file operations by default (Read, Write, Glob).

    Args:
        prompt: The prompt/instructions to send to Claude.
        cwd: Working directory for the agent.
        system_prompt: Optional system prompt.
        timeout_seconds: Maximum time to wait for response.
        allowed_tools: List of allowed tools. Defaults to ["Read", "Write", "Glob"].
        max_turns: Maximum number of conversation turns.

    Returns:
        LLMResult with success status, output text, and list of files written.
    """
    # Set recursion guard
    env_backup = os.environ.get(RECURSION_GUARD_VAR)
    os.environ[RECURSION_GUARD_VAR] = "1"

    try:

        async def _with_timeout() -> tuple[str, list[str]]:
            with anyio.fail_after(timeout_seconds):
                return await _run_agent(
                    prompt,
                    cwd=Path(cwd) if cwd else None,
                    system_prompt=system_prompt,
                    allowed_tools=allowed_tools,
                    max_turns=max_turns,
                )

        output, files = anyio.run(_with_timeout)
        _logger.debug("Agent completed. Files written: %s", files)
        return LLMResult(success=True, output=output, files=files)

    except TimeoutError:
        _logger.warning("Agent call timed out after %ds", timeout_seconds)
        return LLMResult(success=False, error=f"timed out after {timeout_seconds}s")
    except Exception as e:
        _logger.warning("Agent call failed: %s", e)
        return LLMResult(success=False, error=str(e))
    finally:
        # Restore recursion guard
        if env_backup is None:
            os.environ.pop(RECURSION_GUARD_VAR, None)
        else:
            os.environ[RECURSION_GUARD_VAR] = env_backup
