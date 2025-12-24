# Skill Factory Reference

Technical reference for the Skill Factory system that proposes and scaffolds new skills from observed patterns.

## Overview

The Skill Factory analyzes session activity, brain state, and curriculum to identify repeated workflows that could become reusable skills. It then scaffolds these skills with proper SKILL.md files and reference documentation.

## State Files

All state files are stored in `.claude/voyager/`:

| File | Purpose |
|------|---------|
| `skill_proposals.json` | Latest skill proposals from LLM analysis |
| `generated_skills_index.json` | Index of all scaffolded skills |
| `factory.last_update.json` | Debug info for last factory operation |

Generated skills are scaffolded to: `.claude/skills/generated/<skill-name>/`

## CLI Commands

### voyager factory propose

Analyzes patterns to propose new skills.

```bash
# Basic usage (uses brain + curriculum)
voyager factory propose

# Include transcript for richer pattern detection
voyager factory propose --transcript ~/.claude/projects/.../transcript.jsonl

# Dry run (print proposals, don't save)
voyager factory propose --dry-run

# Skip LLM, use existing proposals
voyager factory propose --skip-llm
```

**Inputs:**
- Brain state (`.claude/voyager/brain.json`)
- Curriculum (`.claude/voyager/curriculum.json`)
- Optional: Session transcript

**Output:** `skill_proposals.json` with proposed skills

### voyager factory scaffold

Creates skill folders from proposals.

```bash
# Scaffold first proposal
voyager factory scaffold

# Scaffold specific proposal by name
voyager factory scaffold --name pr-reviewer

# Scaffold by index
voyager factory scaffold --index 2

# Dry run (print scaffold, don't create files)
voyager factory scaffold --dry-run

# Overwrite existing skill
voyager factory scaffold --name my-skill --force
```

### voyager factory list

Lists available proposals.

```bash
voyager factory list
```

**Input:** `skill_proposals.json`

**Output:** Skill folder at `.claude/skills/generated/<name>/`

## Schemas

### skill_proposal.schema.json

Validates skill proposals from the LLM.

```json
{
  "name": "pr-reviewer",
  "description": "Review PRs with structured checklist",
  "triggers": ["review this PR", "check this PR"],
  "rationale": "Pattern observed in 5+ sessions",
  "allowed_tools": ["Read", "Grep", "Glob", "Bash"],
  "suggested_references": ["prompts/checklist.md"],
  "complexity": "moderate",
  "priority": "high"
}
```

**Fields:**
- `name`: Lowercase hyphenated identifier (e.g., `pr-reviewer`)
- `description`: One-line description
- `triggers`: Natural language phrases that invoke this skill
- `rationale`: Why this skill is useful
- `allowed_tools`: Tools the skill needs
- `suggested_references`: Additional files to generate
- `complexity`: `simple` | `moderate` | `complex`
- `priority`: `low` | `medium` | `high`

## Generated Skill Structure

```
.claude/skills/generated/<skill-name>/
├── SKILL.md           # Main skill file with YAML frontmatter
├── reference.md       # Detailed instructions (optional)
└── prompts/           # Prompt templates (optional)
    └── *.md
```

### SKILL.md Format

```yaml
---
name: skill-name
description: |
  Description with trigger phrases:
  - "trigger one"
  - "trigger two"
allowed-tools:
  - Read
  - Grep
  - Glob
---

# Skill Title

Description and workflow.

## When to Use

Context for when this skill applies.

## Workflow

1. Step one
2. Step two

## Examples

Example usage scenarios.
```

## Integration

### Manual Invocation

Users can invoke the factory through natural language:

- "Turn this workflow into a skill"
- "Make a skill for our PR review process"
- "Generate a new skill for X"

### From Brain/Curriculum

The factory can analyze existing state:

```bash
# Propose skills based on current brain state
voyager factory propose

# Include recent session for richer analysis
voyager factory propose --transcript <path>
```

## Guardrails

The factory enforces several safety rules:

1. **No overwrites**: Won't overwrite existing skills without `--force`
2. **Duplicate detection**: Checks existing skills before proposing
3. **Validation**: Validates YAML frontmatter before scaffolding
4. **Bounded scope**: Limits tools to what the skill actually needs

## Troubleshooting

### "No proposals found"

The LLM didn't identify any patterns worth turning into skills. This can happen when:
- Brain state is minimal
- No clear repeated workflows
- Existing skills already cover patterns

Try including a transcript for more context.

### "Proposal validation failed"

The LLM returned invalid JSON. The factory will still attempt to use it, but some fields may be missing. Check `factory.last_update.json` for details.

### "Skill already exists"

Use `--force` to overwrite, or choose a different skill name.

## Best Practices

1. **Review proposals** before scaffolding - not all suggestions are good
2. **Start simple** - scaffold with `--skip-llm` first, then enhance
3. **Test the skill** - verify it works before committing
4. **Refine triggers** - add more natural language variations
5. **Keep it focused** - one skill per workflow, not mega-skills
