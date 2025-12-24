"""Generate embedding text from skill metadata.

The key insight: embeddings should capture HOW USERS ASK FOR THINGS,
not just what the skill does. The example_queries field is critical.
"""

from __future__ import annotations

from voyager.retrieval.analyzer import SkillMetadata


def generate_embedding_text(metadata: SkillMetadata) -> str:
    """Generate rich, searchable text for ColBERT indexing.

    Strategy:
    1. Lead with example queries (most important for retrieval)
    2. Include purpose and capabilities
    3. Add task types for categorical matching
    4. Include file types for specific matches

    Args:
        metadata: Extracted skill metadata.

    Returns:
        Text optimized for embedding-based search.
    """
    sections: list[str] = []

    # Example queries are GOLD - they're exactly what users will search for
    if metadata.example_queries:
        sections.append("Example uses: " + " | ".join(metadata.example_queries))

    # Purpose gives semantic grounding
    if metadata.purpose:
        sections.append(f"Purpose: {metadata.purpose}")

    # Description if different from purpose
    if metadata.description and metadata.description != metadata.purpose:
        # Use first line of description
        first_line = metadata.description.split("\n")[0].strip()
        if first_line and first_line != metadata.purpose:
            sections.append(f"Description: {first_line}")

    # Capabilities for verb matching
    if metadata.capabilities:
        sections.append(f"Can: {', '.join(metadata.capabilities)}")

    # Task types for categorical queries
    if metadata.task_types:
        sections.append(f"Tasks: {', '.join(metadata.task_types)}")

    # File types for specific queries like "edit a .docx"
    if metadata.file_types:
        sections.append(f"File types: {', '.join(metadata.file_types)}")

    # When to use (positive matching)
    if metadata.when_to_use:
        sections.append(f"Use for: {metadata.when_to_use}")

    # Skill name as anchor
    sections.append(f"Skill: {metadata.name}")

    return "\n".join(sections)


def generate_simple_embedding_text(metadata: SkillMetadata) -> str:
    """Generate simpler embedding text when LLM analysis is unavailable.

    Uses only frontmatter data without LLM-extracted fields.

    Args:
        metadata: Extracted skill metadata (may have minimal LLM data).

    Returns:
        Basic text for embedding-based search.
    """
    sections: list[str] = []

    # Name and description
    sections.append(f"Skill: {metadata.name}")

    if metadata.description:
        sections.append(f"Description: {metadata.description}")

    # Allowed tools can hint at capabilities
    if metadata.allowed_tools:
        sections.append(f"Tools: {', '.join(metadata.allowed_tools)}")

    # Use body content (truncated)
    if metadata.raw_body:
        # Take first 500 chars of body
        body_excerpt = metadata.raw_body[:500].strip()
        if body_excerpt:
            sections.append(f"Content: {body_excerpt}")

    return "\n".join(sections)
