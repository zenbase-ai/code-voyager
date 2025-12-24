---
name: skill-factory
description: |
  Self-improving skill library for programming workflows. Mines transcripts and patterns
  to propose and scaffold new skills. Use when you hear:
  - "turn this workflow into a skill"
  - "make a skill for our PR review process"
  - "generate a new skill"
  - "automate this repeated process"
  - "create a skill for X"
  - "what skills could I create?"
  - "propose some skills"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
---

# Skill Factory

Proposes and scaffolds new skills from observed patterns in transcripts and brain state.

## Outputs

- `.claude/skills/generated/<skill-name>/` — scaffolded skill folders
- `.claude/voyager/skill_proposals.json` — latest skill proposals
- `.claude/voyager/generated_skills_index.json` — index of generated skills

## Safe Two-Step Loop

**Always follow this workflow:**

### Step 1: Propose Candidates

Analyze patterns and present **3-5 skill candidates** to the user:

```bash
voyager factory propose
```

- Creates `skill_proposals.json` with candidates
- Present each with name, description, triggers, and rationale
- **Wait for user selection** before proceeding

### Step 2: Scaffold User's Choice

Only scaffold the skill the user explicitly selects:

```bash
# List available proposals
voyager factory list

# Scaffold by name (after user selects)
voyager factory scaffold --name <selected-skill>

# Or by index
voyager factory scaffold --index <n>
```

**Important:** Never scaffold multiple skills automatically. Let the user pick.

## Common Queries

### "What skills could I create?"

1. Read `.claude/voyager/brain.json` to understand recent patterns
2. Run `voyager factory propose --dry-run` to see proposals
3. Present the top 3 proposals with rationale

### "Turn this workflow into a skill"

1. Ask user to describe the workflow
2. Create a manual proposal based on their description
3. Run scaffold_skill.py with the proposal
4. Review and refine the generated SKILL.md

### "Generate a skill for X"

1. Analyze what "X" involves (tools needed, triggers, workflow)
2. Create or find a matching proposal
3. Scaffold the skill
4. Add it to the generated skills index

## Files

| File | Purpose |
|------|---------|
| `schemas/skill_proposal.schema.json` | Validates skill proposals |
| `prompts/propose_skills.prompt.md` | LLM prompt for proposing skills |
| `prompts/scaffold_skill.prompt.md` | LLM prompt for generating SKILL.md |
| `reference.md` | Technical reference |

## Guardrails

- **Never overwrite** existing skills without explicit confirmation
- **Validate** YAML frontmatter before scaffolding
- **Check duplicates** against existing generated skills
- **Keep SKILL.md concise** (< 100 lines, point to references)

See `reference.md` for full implementation details.
