# Code Voyager

**Claude Code that remembers.**

Every session starts from zero. You teach Claude your patterns, refine your prompts, discover what works—then close the terminal and it's gone. Code Voyager fixes this.

Inspired by [Voyager](https://arxiv.org/abs/2305.16291), the Minecraft AI that learns and improves over time, Code Voyager brings three mechanisms to Claude Code: **memory** that persists, **direction** that guides, and **skills** that compound.

### The 5 Skills

| Skill | What it does |
|-------|--------------|
| **Session Brain** | Persistent working memory—tracks your goals, decisions, and progress across sessions |
| **Curriculum Planner** | Generates prioritized task sequences—for onboarding, roadmaps, or refactors |
| **Skill Factory** | Proposes and scaffolds new skills from observed patterns in your workflows |
| **Skill Retrieval** | Semantic search over your skill library using ColBERT late-interaction embeddings |
| **Skill Refinement** | Analyzes tool execution feedback to recommend skill improvements |

The result: an assistant that gets better at helping you the more you use it.

> See [WHY.md](WHY.md) for the full motivation.

## Installation

### Quick Install

```bash
# 1. Install the CLI
uv tool install "git+https://github.com/zenbase-ai/code-voyager.git"

# 2. Install skills to Claude Code (in your project directory)
mkdir -p .claude/skills && \
  curl -sL https://github.com/zenbase-ai/code-voyager/archive/main.tar.gz | \
  tar -xz -C .claude/skills --strip-components=3 code-voyager-main/.claude/skills/

```

Add the following hooks to your project's `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {"matcher": "*", "hooks": [{"type": "command", "command": "voyager hook session-start", "timeout": 10000}]}
    ],
    "PreCompact": [
      {"matcher": "*", "hooks": [{"type": "command", "command": "voyager hook pre-compact", "timeout": 20000}]}
    ],
    "SessionEnd": [
      {"matcher": "*", "hooks": [{"type": "command", "command": "voyager hook session-end", "timeout": 20000}]}
    ],
    "PostToolUse": [
      {"matcher": "*", "hooks": [{"type": "command", "command": "voyager hook post-tool-use", "timeout": 5000}]}
    ]
  }
}
```

### Optional: Semantic Skill Retrieval

For ColBERT-based skill search, install with the retrieval extra:

```bash
uv tool install "git+https://github.com/zenbase-ai/code-voyager.git[retrieval]"
```

### Verify Installation

```bash
# Check skills are available
ls .claude/skills/

# Check CLI works (if installed)
voyager --help

# In Claude Code, ask: "What skills are available?"
```

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

### Manual Smoke Test Checklist

1. **Skill mirror**: `just sync-skills`
2. **Hook simulation**: `just hook-session-start` (validate JSON output)
3. **Brain update**: `just hook-pre-compact` (check `.claude/voyager/brain.json`)
4. **Curriculum plan**: `just curriculum-plan --dry-run`
5. **Factory propose**: `just factory-propose --dry-run`
6. **Factory scaffold**: `just factory-scaffold --name test-skill --dry-run`
7. **Skill index**: `voyager skill index --verbose`
8. **Skill find**: `voyager skill find "resume session"`
9. **Feedback insights**: `voyager feedback insights`

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
voyager feedback insights         # Show skill insights
voyager hook session-start        # SessionStart hook handler
voyager hook session-end          # SessionEnd hook handler
voyager hook pre-compact          # PreCompact hook handler
voyager hook post-tool-use        # PostToolUse hook handler
```

## License

MIT

## Acknowledgments

This was inspired by the Voyager paper:

```bibtex
@article{wang2023voyager,
  title   = {Voyager: An Open-Ended Embodied Agent with Large Language Models},
  author  = {Guanzhi Wang and Yuqi Xie and Yunfan Jiang and Ajay Mandlekar and Chaowei Xiao and Yuke Zhu and Linxi Fan and Anima Anandkumar},
  year    = {2023},
  journal = {arXiv preprint arXiv: Arxiv-2305.16291}
}
```
