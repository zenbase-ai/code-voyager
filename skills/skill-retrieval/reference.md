# Skill Retrieval System — Technical Reference

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SKILL INDEXING PIPELINE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                                │
│  │   SKILL.md   │  (any format)                                  │
│  └──────┬───────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────┐       │
│  │            LLM METADATA EXTRACTOR                     │       │
│  │                                                       │       │
│  │  Extracts:                                            │       │
│  │  • Primary purpose (1 sentence)                       │       │
│  │  • Task types it handles (list)                       │       │
│  │  • File types it works with                           │       │
│  │  • Key capabilities/verbs                             │       │
│  │  • When to use vs not use                             │       │
│  │  • Optimal search queries that should match           │       │
│  │                                                       │       │
│  │  Output: Structured JSON                              │       │
│  └──────────────────┬───────────────────────────────────┘       │
│                     │                                            │
│                     ▼                                            │
│  ┌──────────────────────────────────────────────────────┐       │
│  │            EMBEDDING TEXT GENERATOR                   │       │
│  │                                                       │       │
│  │  Combines LLM-extracted metadata into rich            │       │
│  │  searchable text optimized for ColBERT               │       │
│  └──────────────────┬───────────────────────────────────┘       │
│                     │                                            │
│                     ▼                                            │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              ColBERT INDEX (RAGatouille)              │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Modules

### `voyager.retrieval.discovery`

Auto-discovers skill directories from standard locations:

```python
from voyager.retrieval.discovery import discover_all_skills, discover_skills_roots

# Get all skill root directories
roots = discover_skills_roots()

# Get all skill directories (containing SKILL.md)
skills = discover_all_skills()
```

Search order:
1. `CLAUDE_SKILLS_PATH` environment variable
2. `./skills/` (plugin skills)
3. `./.claude/skills/local/` (local mirror)
4. `./.claude/skills/generated/` (generated skills)
5. `~/.claude/skills/` (user skills)

### `voyager.retrieval.analyzer`

LLM-powered metadata extraction:

```python
from voyager.retrieval.analyzer import analyze_skill, SkillMetadata

metadata: SkillMetadata = analyze_skill(Path("skills/session-brain"))
print(metadata.purpose)
print(metadata.example_queries)
```

`SkillMetadata` fields:
- `skill_id`: Directory name
- `name`: From frontmatter or directory
- `path`: Full path to skill directory
- `description`: From frontmatter
- `allowed_tools`: From frontmatter
- `purpose`: LLM-extracted one-sentence purpose
- `task_types`: LLM-extracted task categories
- `file_types`: LLM-extracted file extensions
- `capabilities`: LLM-extracted action verbs
- `when_to_use`: LLM-extracted usage scenarios
- `when_not_to_use`: LLM-extracted anti-patterns
- `example_queries`: LLM-generated search queries

### `voyager.retrieval.embedding`

Generates embedding text optimized for search:

```python
from voyager.retrieval.embedding import generate_embedding_text

text = generate_embedding_text(metadata)
```

Strategy:
1. Lead with example queries (most important)
2. Include purpose and capabilities
3. Add task types for categorical matching
4. Include file types for specific matches

### `voyager.retrieval.index`

ColBERT index manager:

```python
from voyager.retrieval.index import SkillIndex

index = SkillIndex()

# Build index
count = index.build(verbose=True)

# Search
results = index.search("resume where we left off", k=5)
for r in results:
    print(f"{r.name}: {r.purpose} (score: {r.score:.3f})")
```

## File Structure

```
~/.skill-index/                 # Default index location
├── metadata.json               # Skill metadata for search results
├── simple_index.json           # Fallback text-based index
└── colbert/                    # ColBERT index (when available)
    └── indexes/
        └── claude_skills/
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VOYAGER_SKILL_INDEX_PATH` | Index storage location | `~/.skill-index/` |
| `CLAUDE_SKILLS_PATH` | Override skill discovery | Auto-detect |
| `CLAUDE_PROJECT_DIR` | Project root for relative paths | `cwd` |
| `CLAUDE_PLUGIN_ROOT` | Plugin root for `./skills/` | `cwd` |

## Dependencies

Core:
- `typer` — CLI framework

Optional (for ColBERT):
- `ragatouille>=0.0.8` — ColBERT wrapper

Install with:
```bash
pip install -e ".[retrieval]"
```

Without RAGatouille, falls back to simple text matching.

## Graceful Degradation

When ColBERT/RAGatouille is unavailable:
1. Index build uses simple text-based storage
2. Search uses keyword matching instead of embeddings
3. Results are still ranked by relevance

When LLM analysis fails:
1. Metadata is extracted from YAML frontmatter only
2. Description text is used as fallback example queries
3. Search quality is reduced but functional
