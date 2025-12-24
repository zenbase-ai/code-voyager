"""LLM-powered skill metadata extraction.

Analyzes SKILL.md files to extract structured metadata for semantic search.
Uses the LLM to understand capabilities, task types, and generate example queries.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from voyager.llm import call_claude
from voyager.logging import get_logger

_logger = get_logger("retrieval.analyzer")


@dataclass
class SkillMetadata:
    """Structured metadata extracted from a SKILL.md file."""

    skill_id: str
    name: str
    path: Path

    # From frontmatter
    description: str = ""
    allowed_tools: list[str] = field(default_factory=list)

    # LLM-extracted fields
    purpose: str = ""
    task_types: list[str] = field(default_factory=list)
    file_types: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    when_to_use: str = ""
    when_not_to_use: str = ""
    example_queries: list[str] = field(default_factory=list)

    # Raw content for fallback
    raw_body: str = ""


EXTRACTION_PROMPT = """\
Analyze this Claude Skill definition and extract structured metadata.

<skill_content>
{content}
</skill_content>

Return a JSON object with these fields:
{{
  "purpose": "One sentence describing the primary purpose",
  "task_types": ["list", "of", "task", "categories", "this", "handles"],
  "file_types": ["file", "extensions", "it", "works", "with"],
  "capabilities": ["action", "verbs", "like", "create", "edit", "analyze"],
  "when_to_use": "Describe scenarios when this skill is the right choice",
  "when_not_to_use": "Describe when NOT to use this skill",
  "example_queries": ["example user queries", "that should match this skill"]
}}

Focus on what makes this skill UNIQUE and DISTINGUISHABLE from others.
The example_queries are especially important - generate 5-10 diverse queries.

Return ONLY valid JSON, no markdown formatting or code blocks."""


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown content.

    Args:
        content: Full markdown content.

    Returns:
        Tuple of (frontmatter dict, body content).
    """
    # Match YAML frontmatter between --- markers
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if not match:
        return {}, content

    try:
        import yaml

        fm = yaml.safe_load(match.group(1))
        return fm or {}, match.group(2)
    except Exception as e:
        _logger.warning("Failed to parse frontmatter: %s", e)
        return {}, content


def analyze_skill(
    skill_path: Path,
    *,
    skip_llm: bool = False,
) -> SkillMetadata:
    """Analyze a skill directory to extract metadata.

    Args:
        skill_path: Path to the skill directory containing SKILL.md.
        skip_llm: If True, skip LLM analysis and only use frontmatter.

    Returns:
        SkillMetadata with extracted fields.

    Raises:
        FileNotFoundError: If SKILL.md doesn't exist.
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"No SKILL.md in {skill_path}")

    content = skill_md.read_text()
    frontmatter, body = parse_frontmatter(content)

    # Create base metadata from frontmatter
    metadata = SkillMetadata(
        skill_id=skill_path.name,
        name=frontmatter.get("name", skill_path.name),
        path=skill_path,
        description=frontmatter.get("description", ""),
        allowed_tools=frontmatter.get("allowed-tools", []),
        raw_body=body,
    )

    # Use description as initial purpose
    if metadata.description:
        metadata.purpose = metadata.description.split("\n")[0]
    else:
        metadata.purpose = ""

    if skip_llm:
        # Extract basic info from description trigger phrases
        _extract_triggers_from_description(metadata)
        return metadata

    # Call LLM for rich extraction
    try:
        _logger.debug("Analyzing skill with LLM: %s", skill_path.name)
        prompt = EXTRACTION_PROMPT.format(content=content[:8000])  # Truncate if huge

        result = call_claude(
            prompt,
            system_prompt="You are a skill analyzer. Extract metadata as JSON.",
            allowed_tools=[],  # No tools needed, just text response
            max_turns=1,
            timeout_seconds=30,
        )

        if result.success and result.output:
            # Parse JSON from output
            extracted = _parse_json_response(result.output)
            if extracted:
                metadata.purpose = extracted.get("purpose", metadata.purpose)
                metadata.task_types = extracted.get("task_types", [])
                metadata.file_types = extracted.get("file_types", [])
                metadata.capabilities = extracted.get("capabilities", [])
                metadata.when_to_use = extracted.get("when_to_use", "")
                metadata.when_not_to_use = extracted.get("when_not_to_use", "")
                metadata.example_queries = extracted.get("example_queries", [])
        else:
            _logger.warning("LLM call failed for %s: %s", skill_path.name, result.error)
            _extract_triggers_from_description(metadata)

    except Exception as e:
        _logger.warning("LLM extraction failed for %s: %s", skill_path.name, e)
        _extract_triggers_from_description(metadata)

    return metadata


def _parse_json_response(text: str) -> dict | None:
    """Parse JSON from LLM response, handling common issues."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find JSON object in text
    brace_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _extract_triggers_from_description(metadata: SkillMetadata) -> None:
    """Extract trigger phrases from description as fallback example queries."""
    desc = metadata.description.lower()

    # Common trigger patterns
    trigger_patterns = [
        r"use when you want to[:\s]*(.*)",
        r"helps? (?:you )?(.*)",
        r"used? (?:for|to) (.*)",
    ]

    for pattern in trigger_patterns:
        match = re.search(pattern, desc)
        if match:
            triggers = match.group(1)
            # Split on common delimiters
            for trigger in re.split(r"[,\n•\-]", triggers):
                trigger = trigger.strip()
                if trigger and len(trigger) > 5:
                    metadata.example_queries.append(trigger)

    # Use description lines as basic examples
    if not metadata.example_queries and metadata.description:
        lines = [
            line.strip()
            for line in metadata.description.split("\n")
            if line.strip() and not line.strip().startswith("-")
        ]
        metadata.example_queries = lines[:5]
