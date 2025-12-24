"""Voyager: Meta-skills for Coding Agents.

This package provides:
- Skill retrieval system using ColBERT embeddings
- Feedback collection and skill refinement
- Shared utilities for hooks and scripts
"""

__version__ = "0.1.0"

# Re-export commonly used utilities
from voyager.io import (
    ensure_parent_dir,
    read_file,
    read_json,
    write_file,
    write_json,
)
from voyager.logging import get_logger

__all__ = [
    "ensure_parent_dir",
    "get_logger",
    "read_file",
    "read_json",
    "write_file",
    "write_json",
]
