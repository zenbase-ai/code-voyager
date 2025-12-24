"""Semantic skill detector for tool execution attribution.

Detects which skill is being used based on tool execution context using
a cascade of strategies (no hardcoded mappings):

1. Transcript context - check if Claude read a SKILL.md
2. Learned associations - fast lookup from past attributions
3. ColBERT index query - semantic matching via find-skill
4. LLM inference - fallback for unknown patterns
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from voyager.config import get_feedback_db_path
from voyager.logging import get_logger

_logger = get_logger("refinement.detector")


class SkillDetector:
    """Semantically detect which skill is being used from tool execution context.

    Uses a cascade of strategies, from most accurate to most general,
    with no hardcoded mappings.
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        use_llm: bool = True,
        llm_timeout: int = 30,
    ):
        """Initialize the detector.

        Args:
            db_path: Path to feedback database for learned associations.
            use_llm: Whether to use LLM inference as fallback.
            llm_timeout: Timeout for LLM calls in seconds.
        """
        if db_path is None:
            db_path = get_feedback_db_path()
        self.db_path = Path(db_path)
        self.use_llm = use_llm
        self.llm_timeout = llm_timeout

        # Lazy-loaded store for learned associations
        self._store: Any = None
        self._colbert_available: bool | None = None

    @property
    def store(self) -> Any:
        """Lazy-load the feedback store."""
        if self._store is None:
            from voyager.refinement.store import FeedbackStore

            self._store = FeedbackStore(self.db_path)
        return self._store

    def detect(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        transcript_path: str | Path | None = None,
        session_context: str | None = None,
    ) -> str | None:
        """Detect which skill is being used.

        Tries multiple strategies in order of preference:
        1. Transcript context (most accurate - Claude explicitly read a skill)
        2. Learned associations (fast, from past sessions)
        3. ColBERT index query (semantic, if available)
        4. LLM inference (slowest, but works for anything)

        Args:
            tool_name: Name of the tool being used (e.g., "Write", "Bash").
            tool_input: Tool input parameters.
            transcript_path: Path to session transcript JSONL.
            session_context: Optional additional context about the session.

        Returns:
            skill_id or None if uncertain.
        """
        # Strategy 1: Check transcript for explicit skill reading
        if transcript_path:
            skill = self._detect_from_transcript(transcript_path)
            if skill:
                _logger.debug("Detected skill from transcript: %s", skill)
                return skill

        # Strategy 2: Check learned associations
        context_key = self._make_context_key(tool_name, tool_input)
        learned_skill = self.store.get_learned_association(context_key)
        if learned_skill:
            _logger.debug("Detected skill from learned association: %s", learned_skill)
            return learned_skill

        # Strategy 3: Query ColBERT index
        if self._is_colbert_available():
            skill = self._detect_via_colbert(tool_name, tool_input)
            if skill:
                self.store.learn_association(context_key, skill, confidence=0.8)
                _logger.debug("Detected skill from ColBERT: %s", skill)
                return skill

        # Strategy 4: LLM inference (expensive but comprehensive)
        if self.use_llm:
            skill = self._detect_via_llm(tool_name, tool_input, session_context)
            if skill:
                self.store.learn_association(context_key, skill, confidence=0.6)
                _logger.debug("Detected skill from LLM: %s", skill)
                return skill

        _logger.debug("Could not detect skill for %s", tool_name)
        return None

    def _detect_from_transcript(self, transcript_path: str | Path) -> str | None:
        """Check the session transcript for skill file reads.

        If Claude read a SKILL.md file earlier in the session,
        we know that skill is being used.

        Args:
            transcript_path: Path to transcript JSONL.

        Returns:
            skill_id or None.
        """
        try:
            transcript = Path(transcript_path)
            if not transcript.exists():
                return None

            skill_reads: list[str] = []
            for line in transcript.read_text().splitlines():
                try:
                    entry = json.loads(line)
                    # Look for file reads of SKILL.md
                    if entry.get("tool_name") == "Read":
                        path = entry.get("tool_input", {}).get("file_path", "")
                        if "SKILL.md" in path:
                            # Extract skill ID from path
                            # e.g., "/mnt/skills/docx/SKILL.md" -> "docx"
                            # or "skills/session-brain/SKILL.md" -> "session-brain"
                            parts = Path(path).parts
                            if "skills" in parts:
                                idx = list(parts).index("skills")
                                if idx + 1 < len(parts) - 1:
                                    skill_reads.append(parts[idx + 1])
                except json.JSONDecodeError:
                    continue

            # Return most recently read skill
            return skill_reads[-1] if skill_reads else None

        except Exception as e:
            _logger.debug("Error reading transcript: %s", e)
            return None

    def _detect_via_colbert(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> str | None:
        """Query the skill retrieval index for skill matching.

        Args:
            tool_name: Tool being used.
            tool_input: Tool parameters.

        Returns:
            skill_id or None.
        """
        try:
            # Construct a natural query from tool context
            query = self._tool_context_to_query(tool_name, tool_input)

            # Call the find-skill CLI
            result = subprocess.run(
                ["find-skill", query, "-k", "1", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                results = json.loads(result.stdout)
                if results and len(results) > 0:
                    # Check confidence threshold
                    score = results[0].get("score", 0)
                    if score > 0.5:
                        return results[0].get("skill_id") or results[0].get("name")

            return None

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            _logger.debug("ColBERT query failed: %s", e)
            return None
        except Exception as e:
            _logger.debug("Unexpected error in ColBERT detection: %s", e)
            return None

    def _detect_via_llm(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        session_context: str | None = None,
    ) -> str | None:
        """Use LLM to infer which skill is being used.

        Args:
            tool_name: Tool being used.
            tool_input: Tool parameters.
            session_context: Optional additional context.

        Returns:
            skill_id or None.
        """
        try:
            prompt = self._build_detection_prompt(tool_name, tool_input, session_context)
            command = self._get_llm_command()

            if command is None:
                _logger.debug("No LLM command available")
                return None

            result = subprocess.run(
                [*command, prompt],
                capture_output=True,
                text=True,
                timeout=self.llm_timeout,
            )

            if result.returncode == 0:
                response = result.stdout.strip()
                return self._parse_skill_from_response(response)

            return None

        except subprocess.TimeoutExpired:
            _logger.debug("LLM call timed out")
            return None
        except Exception as e:
            _logger.debug("LLM detection failed: %s", e)
            return None

    def _tool_context_to_query(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> str:
        """Convert tool execution context to a natural language query.

        Args:
            tool_name: Tool being used.
            tool_input: Tool parameters.

        Returns:
            Natural language query string.
        """
        parts: list[str] = []

        # File path gives strong signal
        file_path = tool_input.get("file_path", "")
        if file_path:
            ext = Path(file_path).suffix
            if ext:
                parts.append(f"working with {ext} files")

        # Command content for Bash
        command = tool_input.get("command", "")
        if command:
            # Look for common patterns
            command_lower = command.lower()
            if "python" in command_lower:
                parts.append("python script")
            if "git" in command_lower:
                parts.append("git operations")
            if "npm" in command_lower or "node" in command_lower:
                parts.append("node.js")
            # Look for library names
            for lib in ["docx", "pdf", "xlsx", "pptx", "pandas", "openpyxl"]:
                if lib in command_lower:
                    parts.append(f"using {lib}")

        # Tool name context
        tool_descriptions = {
            "Write": "creating or writing files",
            "Edit": "editing existing files",
            "Bash": "running commands",
            "Read": "reading file contents",
            "Glob": "finding files",
            "Grep": "searching code",
        }
        if tool_name in tool_descriptions:
            parts.append(tool_descriptions[tool_name])

        return " ".join(parts) if parts else f"using {tool_name} tool"

    def _build_detection_prompt(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        session_context: str | None,
    ) -> str:
        """Build prompt for LLM skill detection.

        Args:
            tool_name: Tool being used.
            tool_input: Tool parameters.
            session_context: Optional additional context.

        Returns:
            Prompt string.
        """
        # Truncate long inputs
        input_str = json.dumps(tool_input, indent=2)
        if len(input_str) > 1000:
            input_str = input_str[:1000] + "..."

        context_part = ""
        if session_context:
            context_part = f"\nSession context: {session_context[:500]}"

        return f"""Given this Claude Code tool execution, identify which skill is likely being used.

Tool: {tool_name}
Input: {input_str}{context_part}

Common Claude Skills include:
- session-brain: session memory and context recall
- curriculum-planner: planning and task organization
- skill-factory: creating new skills
- skill-retrieval: finding relevant skills
- skill-refinement: feedback and improvement

Return ONLY the skill ID (e.g., "session-brain") or "unknown" if uncertain.
Do not explain, just return the skill ID."""

    def _get_llm_command(self) -> list[str] | None:
        """Get command to invoke available LLM.

        Returns:
            Command list or None if no LLM available.
        """
        if shutil.which("claude"):
            return ["claude", "-p"]
        if shutil.which("llm"):
            return ["llm"]
        return None

    def _parse_skill_from_response(self, response: str) -> str | None:
        """Extract skill ID from LLM response.

        Args:
            response: LLM response text.

        Returns:
            Cleaned skill ID or None.
        """
        response = response.strip().lower()
        if response == "unknown" or not response:
            return None

        # Clean up common response patterns
        response = response.replace('"', "").replace("'", "")
        if response.startswith("skill:"):
            response = response[6:].strip()

        # Validate it looks like a skill ID (reasonable length, alphanumeric+dash)
        if len(response) < 50 and all(c.isalnum() or c == "-" for c in response):
            return response

        return None

    def _make_context_key(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Create a hashable key from tool context for learning.

        Args:
            tool_name: Tool being used.
            tool_input: Tool parameters.

        Returns:
            Context key string.
        """
        # Use file extension and tool name as key
        file_path = tool_input.get("file_path", "")
        ext = Path(file_path).suffix if file_path else ""

        # First 50 chars of command for Bash
        command = tool_input.get("command", "")[:50]

        return f"{tool_name}|{ext}|{command}"

    def _is_colbert_available(self) -> bool:
        """Check if the skill retrieval index is available.

        Returns:
            True if find-skill command exists.
        """
        if self._colbert_available is None:
            self._colbert_available = shutil.which("find-skill") is not None
        return self._colbert_available
