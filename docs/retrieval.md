# ColBERT-based Skill Retrieval System

## Project Vision

Build a **Voyager-inspired skill retrieval system** for Claude Skills that uses ColBERT (via RAGatouille) to semantically search and retrieve relevant skills. This version uses **LLM-powered indexing** to automatically extract capabilities from any SKILL.md file—no manual configuration required.

> **Design Principle**: If it requires domain knowledge, use an LLM. If it requires speed, use embeddings. Combine both.

---

## Quick Start

```bash
# Install
pip install -e .

# Index all skills (auto-discovers location)
skill-index

# Search for relevant skills
find-skill "create a PDF report from spreadsheet data"
```

That's it. No configuration files, no manual mappings.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SKILL INDEXING PIPELINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐                                               │
│  │   SKILL.md   │  (any format)                                 │
│  └──────┬───────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────────────────────────────────────────┐      │
│  │            LLM METADATA EXTRACTOR                     │      │
│  │                                                       │      │
│  │  Prompt: "Analyze this skill and extract:"            │      │
│  │  • Primary purpose (1 sentence)                       │      │
│  │  • Task types it handles (list)                       │      │
│  │  • File types it works with                           │      │
│  │  • Key capabilities/verbs                             │      │
│  │  • When to use vs not use                             │      │
│  │  • Optimal search queries that should match           │      │
│  │                                                       │      │
│  │  Output: Structured JSON                              │      │
│  └──────────────────┬───────────────────────────────────┘      │
│                     │                                           │
│                     ▼                                           │
│  ┌──────────────────────────────────────────────────────┐      │
│  │            EMBEDDING TEXT GENERATOR                   │      │
│  │                                                       │      │
│  │  Combines LLM-extracted metadata into rich            │      │
│  │  searchable text optimized for ColBERT               │      │
│  └──────────────────┬───────────────────────────────────┘      │
│                     │                                           │
│                     ▼                                           │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              ColBERT INDEX (RAGatouille)              │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Implementation

### 1. LLM-Powered Skill Analyzer (`skill_analyzer.py`)

```python
"""
Use an LLM to extract structured metadata from any SKILL.md file.

This replaces hardcoded regex patterns with semantic understanding.
Works with ANY skill format - the LLM figures out what matters.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
import subprocess

@dataclass
class SkillMetadata:
    """Structured metadata extracted by LLM."""
    skill_id: str
    name: str
    path: Path

    # LLM-extracted fields
    purpose: str = ""
    task_types: List[str] = field(default_factory=list)
    file_types: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    when_to_use: str = ""
    when_not_to_use: str = ""
    example_queries: List[str] = field(default_factory=list)

    # Raw content for fallback
    raw_description: str = ""
    raw_body: str = ""

EXTRACTION_PROMPT = '''Analyze this Claude Skill definition and extract structured metadata.

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

Return ONLY valid JSON, no markdown formatting.'''

def analyze_skill_with_llm(skill_path: Path, llm_command: str = None) -> SkillMetadata:
    """
    Use an LLM to extract metadata from a SKILL.md file.

    Args:
        skill_path: Path to skill directory containing SKILL.md
        llm_command: Command to invoke LLM (default: auto-detect)

    Returns:
        SkillMetadata with LLM-extracted fields populated
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"No SKILL.md in {skill_path}")

    content = skill_md.read_text()

    # Extract basic info from frontmatter if present
    name, description, body = parse_frontmatter(content)

    # Create base metadata
    metadata = SkillMetadata(
        skill_id=skill_path.name,
        name=name or skill_path.name,
        path=skill_path,
        raw_description=description,
        raw_body=body
    )

    # Call LLM for rich extraction
    try:
        llm_response = call_llm(
            EXTRACTION_PROMPT.format(content=content[:8000]),  # Truncate if huge
            llm_command=llm_command
        )

        extracted = json.loads(llm_response)

        metadata.purpose = extracted.get("purpose", "")
        metadata.task_types = extracted.get("task_types", [])
        metadata.file_types = extracted.get("file_types", [])
        metadata.capabilities = extracted.get("capabilities", [])
        metadata.when_to_use = extracted.get("when_to_use", "")
        metadata.when_not_to_use = extracted.get("when_not_to_use", "")
        metadata.example_queries = extracted.get("example_queries", [])

    except Exception as e:
        # Fallback: use raw content
        print(f"LLM extraction failed for {skill_path.name}: {e}")
        metadata.purpose = description

    return metadata

def call_llm(prompt: str, llm_command: str = None) -> str:
    """
    Call an LLM to process a prompt. Auto-detects available LLM.

    Supports:
    - Claude CLI: `claude -p "prompt"`
    - OpenAI CLI: `openai api chat.completions.create -m gpt-4 -g user "prompt"`
    - Ollama: `ollama run llama3 "prompt"`
    - Custom command via llm_command parameter
    """
    if llm_command:
        cmd = llm_command.replace("{prompt}", prompt)
    else:
        # Auto-detect available LLM
        cmd = detect_llm_command(prompt)

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        raise RuntimeError(f"LLM call failed: {result.stderr}")

    return result.stdout.strip()

def detect_llm_command(prompt: str) -> str:
    """Auto-detect available LLM and return appropriate command."""
    import shutil

    # Escape prompt for shell
    escaped = prompt.replace("'", "'\\''")

    # Try Claude CLI first (fastest for Anthropic users)
    if shutil.which("claude"):
        return f"claude -p '{escaped}' --output-format text"

    # Try llm CLI (Simon Willison's tool - supports many backends)
    if shutil.which("llm"):
        return f"llm '{escaped}'"

    # Try Ollama (local)
    if shutil.which("ollama"):
        return f"ollama run llama3 '{escaped}'"

    raise RuntimeError(
        "No LLM CLI found. Install one of:\n"
        "  - claude (Anthropic CLI)\n"
        "  - llm (pip install llm)\n"
        "  - ollama (https://ollama.ai)\n"
        "Or pass llm_command parameter."
    )

def parse_frontmatter(content: str) -> tuple[Optional[str], Optional[str], str]:
    """Extract YAML frontmatter if present."""
    import re
    import yaml

    match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
    if not match:
        return None, None, content

    try:
        fm = yaml.safe_load(match.group(1))
        return fm.get("name"), fm.get("description"), match.group(2)
    except:
        return None, None, content
```

### 2. Smart Embedding Text Generation (`embedding_generator.py`)

```python
"""
Generate optimal embedding text from LLM-extracted metadata.

The key insight: we want the embedding to capture HOW USERS ASK FOR THINGS,
not just what the skill does. The example_queries field is critical.
"""

from skill_analyzer import SkillMetadata

def generate_embedding_text(metadata: SkillMetadata) -> str:
    """
    Generate rich, searchable text for ColBERT indexing.

    Strategy:
    1. Lead with example queries (most important for retrieval)
    2. Include purpose and capabilities
    3. Add task types for categorical matching
    4. Include file types for specific matches
    """
    sections = []

    # Example queries are GOLD - they're exactly what users will search for
    if metadata.example_queries:
        sections.append("Example uses: " + " | ".join(metadata.example_queries))

    # Purpose gives semantic grounding
    if metadata.purpose:
        sections.append(f"Purpose: {metadata.purpose}")

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
```

### 3. Auto-Discovery (`discovery.py`)

```python
"""
Auto-discover skills from common locations. No configuration needed.
"""

from pathlib import Path
from typing import List, Optional
import os

def discover_skills_directory() -> Path:
    """
    Auto-discover the skills directory from environment or common locations.

    Search order:
    1. CLAUDE_SKILLS_PATH environment variable
    2. /mnt/skills (Claude Code standard)
    3. ~/.claude/skills (user skills)
    4. ./skills (project-local)
    """
    # Check environment variable
    env_path = os.environ.get("CLAUDE_SKILLS_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    # Common locations
    candidates = [
        Path("/mnt/skills"),
        Path.home() / ".claude" / "skills",
        Path("./skills"),
        Path("./.skills"),
    ]

    for candidate in candidates:
        if candidate.exists() and any(candidate.rglob("SKILL.md")):
            return candidate

    raise RuntimeError(
        "Could not find skills directory. Either:\n"
        "  - Set CLAUDE_SKILLS_PATH environment variable\n"
        "  - Create skills in /mnt/skills, ~/.claude/skills, or ./skills"
    )

def discover_all_skills(root: Path = None) -> List[Path]:
    """
    Find all skill directories (containing SKILL.md).

    Args:
        root: Root directory to search (default: auto-discover)

    Returns:
        List of paths to skill directories
    """
    if root is None:
        root = discover_skills_directory()

    skills = []
    for skill_md in root.rglob("SKILL.md"):
        skills.append(skill_md.parent)

    return skills
```

### 4. Unified Index Manager (`skill_index.py`)

```python
"""
ColBERT index manager with LLM-powered enrichment.
"""

from ragatouille import RAGPretrainedModel
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

from skill_analyzer import analyze_skill_with_llm, SkillMetadata
from embedding_generator import generate_embedding_text
from discovery import discover_all_skills, discover_skills_directory

class SkillIndex:
    def __init__(
        self,
        index_path: Path = None,
        model_name: str = "colbert-ir/colbertv2.0"
    ):
        # Default to ~/.skill-index for persistence across projects
        self.index_path = index_path or (Path.home() / ".skill-index")
        self.model_name = model_name
        self.index_name = "claude_skills"
        self.rag: Optional[RAGPretrainedModel] = None
        self.metadata_path = self.index_path / "metadata.json"
        self._metadata: Dict[str, Any] = {}

    def build_index(
        self,
        skills_root: Path = None,
        llm_command: str = None,
        force: bool = False
    ):
        """
        Build the ColBERT index with LLM-extracted metadata.

        Args:
            skills_root: Root directory containing skills (default: auto-discover)
            llm_command: Custom LLM command (default: auto-detect)
            force: Rebuild even if index exists
        """
        # Auto-discover if not specified
        if skills_root is None:
            skills_root = discover_skills_directory()

        print(f"📁 Discovering skills in {skills_root}")
        skill_paths = discover_all_skills(skills_root)
        print(f"   Found {len(skill_paths)} skills")

        # Check if rebuild needed
        index_dir = self.index_path / "colbert" / "indexes" / self.index_name
        if index_dir.exists() and not force:
            print(f"✓ Index exists. Use --force to rebuild.")
            return

        # Analyze each skill with LLM
        print(f"🤖 Analyzing skills with LLM...")
        analyzed_skills: List[SkillMetadata] = []

        for i, skill_path in enumerate(skill_paths, 1):
            print(f"   [{i}/{len(skill_paths)}] {skill_path.name}...", end=" ")
            try:
                metadata = analyze_skill_with_llm(skill_path, llm_command)
                analyzed_skills.append(metadata)
                print("✓")
            except Exception as e:
                print(f"⚠ {e}")

        # Generate embeddings text
        print(f"📝 Generating embedding text...")
        documents = []
        doc_ids = []
        doc_metadata = []

        for skill in analyzed_skills:
            embed_text = generate_embedding_text(skill)
            documents.append(embed_text)
            doc_ids.append(skill.skill_id)
            doc_metadata.append({
                "name": skill.name,
                "purpose": skill.purpose,
                "path": str(skill.path),
                "file_types": skill.file_types,
                "capabilities": skill.capabilities
            })

            # Store full metadata
            self._metadata[skill.skill_id] = {
                **doc_metadata[-1],
                "task_types": skill.task_types,
                "when_to_use": skill.when_to_use,
                "example_queries": skill.example_queries
            }

        # Create ColBERT index
        print(f"🔨 Building ColBERT index...")
        self.rag = RAGPretrainedModel.from_pretrained(self.model_name)
        self.rag.index(
            collection=documents,
            document_ids=doc_ids,
            document_metadatas=doc_metadata,
            index_name=self.index_name,
            max_document_length=256,
            split_documents=True
        )

        # Save metadata
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path.write_text(json.dumps(self._metadata, indent=2))

        print(f"✅ Index built: {len(analyzed_skills)} skills indexed")

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for skills matching a query."""
        self._load_index()

        results = self.rag.search(query=query, k=k)

        enriched = []
        for result in results:
            skill_id = result.get("document_id", result.get("doc_id"))
            meta = self._metadata.get(skill_id, {})

            enriched.append({
                "skill_id": skill_id,
                "name": meta.get("name", skill_id),
                "purpose": meta.get("purpose", ""),
                "path": meta.get("path", ""),
                "score": result.get("score", 0.0),
                "file_types": meta.get("file_types", []),
                "capabilities": meta.get("capabilities", [])
            })

        return enriched

    def _load_index(self):
        """Load existing index."""
        if self.rag is not None:
            return

        index_dir = self.index_path / "colbert" / "indexes" / self.index_name
        if not index_dir.exists():
            raise RuntimeError("No index found. Run `skill-index` first.")

        self.rag = RAGPretrainedModel.from_index(str(index_dir))

        if self.metadata_path.exists():
            self._metadata = json.loads(self.metadata_path.read_text())
```

### 5. CLI (`cli.py`)

```python
#!/usr/bin/env python3
"""
Skill retrieval CLI.

Commands:
    skill-index          Build/rebuild the skill index
    find-skill QUERY     Find skills matching a query
"""

import argparse
import json
import sys
from pathlib import Path

from skill_index import SkillIndex

def cmd_index(args):
    """Build the skill index."""
    index = SkillIndex()
    index.build_index(
        skills_root=Path(args.path) if args.path else None,
        llm_command=args.llm,
        force=args.force
    )

def cmd_search(args):
    """Search for skills."""
    index = SkillIndex()
    results = index.search(args.query, k=args.k)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\n🔍 Skills matching: \"{args.query}\"\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['name']} (score: {r['score']:.3f})")
            print(f"   {r['purpose'][:80]}...")
            print(f"   Path: {r['path']}")
            print()

def main():
    parser = argparse.ArgumentParser(description="Claude Skill Retrieval")
    subparsers = parser.add_subparsers(dest="command")

    # Index command
    idx = subparsers.add_parser("index", help="Build skill index")
    idx.add_argument("--path", help="Skills directory path")
    idx.add_argument("--llm", help="Custom LLM command")
    idx.add_argument("--force", action="store_true", help="Force rebuild")
    idx.set_defaults(func=cmd_index)

    # Search command (also default)
    search = subparsers.add_parser("search", help="Search for skills")
    search.add_argument("query", help="Search query")
    search.add_argument("-k", type=int, default=5, help="Number of results")
    search.add_argument("--json", action="store_true", help="JSON output")
    search.set_defaults(func=cmd_search)

    args = parser.parse_args()

    # Handle bare query (no subcommand)
    if args.command is None:
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            # Treat as search query
            args.query = " ".join(sys.argv[1:])
            args.k = 5
            args.json = False
            cmd_search(args)
        else:
            parser.print_help()
    else:
        args.func(args)

if __name__ == "__main__":
    main()
```

---

## Installation

```bash
# Clone and install
git clone <repo>
cd pattern1-colbert-skill-retrieval
pip install -e .

# Build index (one-time, uses LLM)
skill-index

# Search (instant, no LLM needed)
find-skill "convert spreadsheet to PDF"
```

---

## How It Works

### Indexing (One-time, ~30s per skill)

1. **Discover** skills from standard locations
2. **Analyze** each SKILL.md with LLM → structured metadata
3. **Generate** rich embedding text from metadata
4. **Index** with ColBERT for fast retrieval

### Search (Instant, no LLM)

1. Query goes directly to ColBERT index
2. Token-level matching finds relevant skills
3. Return ranked results with metadata

---

## Why LLM-Powered Indexing?

| Approach | Pros | Cons |
|----------|------|------|
| Regex patterns | Fast, no API calls | Brittle, misses semantic meaning |
| Raw text embedding | Simple | Noisy, poor retrieval quality |
| **LLM extraction** | Semantic understanding, generates good search queries | Slower indexing (one-time cost) |

The key insight: **indexing happens once, search happens constantly**. Investing LLM compute at index time pays dividends in retrieval quality.

---

## Configuration (Optional)

Everything works with zero configuration, but you can customize:

```bash
# Environment variables
export CLAUDE_SKILLS_PATH=/custom/path/to/skills
export SKILL_INDEX_PATH=/custom/index/location

# Or pass to commands
skill-index --path /my/skills --llm "ollama run mistral"
```

---

## File Structure

```
pattern1-colbert-skill-retrieval/
├── CLAUDE.md
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── skill_analyzer.py      # LLM-powered metadata extraction
│   ├── embedding_generator.py # Generate searchable text
│   ├── discovery.py           # Auto-discover skills
│   ├── skill_index.py         # ColBERT index manager
│   └── cli.py                 # CLI entry points
└── tests/
```

---

## Dependencies

```toml
[project]
name = "claude-skill-retrieval"
version = "0.2.0"
dependencies = [
    "ragatouille>=0.0.8",
    "pyyaml>=6.0",
    "torch>=2.0.0",
]
```

LLM CLI is **not** a dependency—it's detected at runtime from what's available on your system.
