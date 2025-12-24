# Code Voyager

Meta-skills for Coding Agents: persistent session memory, curriculum planning, skill generation, retrieval, and refinement.

## Installation

### 1. Install the Python package

```bash
# Using uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .

# For semantic skill retrieval (ColBERT), include the optional dependency:
uv pip install -e ".[retrieval]"
```

### 2. Install as a Claude Code plugin

```bash
# Add the plugin to Claude Code
claude plugins add /path/to/voyager
```

### 3. Enable hooks (optional but recommended)

Hooks automatically inject session context and persist brain state. Enable them in your Claude Code settings or use the project-local configuration.

## Artifact Storage

All runtime artifacts are stored under `.claude/voyager/`:

| Path | Description |
|------|-------------|
| `.claude/voyager/brain.json` | Session brain state (structured) |
| `.claude/voyager/brain.md` | Session brain (human-readable) |
| `.claude/voyager/episodes/` | Historical session snapshots |
| `.claude/voyager/curriculum.json` | Curriculum plan (structured) |
| `.claude/voyager/curriculum.md` | Curriculum plan (human-readable) |
| `.claude/voyager/skill_proposals.json` | Pending skill proposals |
| `.claude/voyager/generated_skills_index.json` | Index of generated skills |
| `.claude/voyager/feedback.db` | Tool execution feedback (SQLite) |
| `.claude/voyager/skill-index/` | ColBERT skill index |

Generated skills are stored under `.claude/skills/generated/<skill-name>/`.

## The 5 Skills

### 1. Session Brain

Persistent working memory for coding sessions. Automatically tracks what you're doing, decisions made, and what's next.

**Trigger phrases:**
- "resume where we left off"
- "what were we doing?"
- "remember this decision: ..."
- "what's next?"

**CLI:**
```bash
voyager brain update --transcript session.jsonl  # Update brain from transcript
voyager brain inject                              # Inject brain context (for hooks)
```

### 2. Curriculum Planner

Generates structured learning/improvement plans based on repo state.

**Trigger phrases:**
- "what should I work on next?"
- "create a plan for this repo"
- "help me onboard to this codebase"
- "write the curriculum to disk"

**CLI:**
```bash
voyager curriculum plan                    # Generate curriculum (dry-run by default)
voyager curriculum plan --output .claude/voyager/  # Write artifacts to disk
```

### 3. Skill Factory

Proposes and scaffolds new skills from observed patterns.

**Trigger phrases:**
- "turn this workflow into a skill"
- "what skills could I create?"
- "propose some skills"

**CLI:**
```bash
voyager factory propose                    # Propose skills from patterns
voyager factory list                       # List pending proposals
voyager factory scaffold --name my-skill   # Scaffold a specific skill
```

### 4. Skill Retrieval

Semantic search over skill libraries using ColBERT embeddings.

**Trigger phrases:**
- "find a skill for..."
- "what skill handles..."
- "index my skills"

**CLI:**
```bash
voyager skill index --verbose              # Build the skill index
voyager skill find "query"                 # Search for skills
```

### 5. Skill Refinement

Feedback-driven skill improvement through tool outcome analysis.

**Trigger phrases:**
- "show skill feedback"
- "skill insights"
- "which skills need improvement"

**CLI:**
```bash
voyager feedback setup                     # Install PostToolUse hook
voyager feedback insights                  # Generate improvement recommendations
```

## Dogfooding (Development)

This repo is its own testbed. All features are verifiable locally.

### Quick Start

```bash
# Install dev dependencies
uv pip install -e ".[dev,retrieval]"

# Sync skills to local mirror
just sync-skills

# Run linting and tests
just lint
just test
```

### Hook Simulation (Fixture-Driven Testing)

Test hooks without running Claude Code by piping fixture JSON:

```bash
# Test SessionStart hook (context injection)
just hook-session-start

# Test PreCompact hook (brain update)
just hook-pre-compact

# Test SessionEnd hook (brain update)
just hook-session-end
```

Fixtures are located at `.claude/fixtures/hooks/`.

### Project-Local Hooks

The repo includes project-local hook wrappers in `.claude/hooks/` that delegate to the plugin hooks. These are configured in `.claude/settings.local.json` so you can test without modifying global Claude Code settings.

### Manual Smoke Test Checklist

1. **Skill mirror**: `just sync-skills`
2. **Hook simulation**: `just hook-session-start` (validate JSON output)
3. **Brain update**: `just hook-pre-compact` (check `.claude/voyager/brain.json`)
4. **Curriculum plan**: `just curriculum-plan --dry-run`
5. **Factory propose**: `just factory-propose --dry-run`
6. **Factory scaffold**: `just factory-scaffold --name test-skill --dry-run`
7. **Skill index**: `voyager skill index --verbose`
8. **Skill find**: `voyager skill find "resume session"`
9. **Feedback setup**: `voyager feedback setup`
10. **Feedback insights**: `voyager feedback insights`

## Safety Guarantees

- **Bounded writes**: Scripts only write to `.claude/voyager/` and `.claude/skills/generated/`
- **No destructive commands**: Hooks never run `rm -rf`, `git push --force`, or similar
- **Graceful degradation**: Missing prerequisites (git, claude CLI, ColBERT) don't crash hooks
- **Recursion guard**: LLM sub-calls are protected by `VOYAGER_FOR_CODE_INTERNAL` env var

## CLI Reference

```bash
voyager --help                    # Show all commands
voyager repo snapshot             # Generate repo snapshot
voyager brain update              # Update brain from transcript
voyager brain inject              # Inject brain context
voyager curriculum plan           # Generate curriculum
voyager factory propose           # Propose new skills
voyager factory scaffold          # Scaffold a skill
voyager factory list              # List skill proposals
voyager skill index               # Build skill index
voyager skill find "query"        # Search skills
voyager feedback setup            # Install feedback hook
voyager feedback insights         # Show skill insights
```

## License

MIT
