# Scaffold Skill Prompt

You are generating the content for a new Claude Code skill. Given a skill proposal, produce the SKILL.md file content and any necessary reference files.

## Instructions

1. **Write SKILL.md**: Create the main skill file with YAML frontmatter
2. **Add instructions**: Clear, actionable guidance for Claude
3. **Reference external files**: If the skill needs prompts, schemas, or scripts
4. **Keep it concise**: SKILL.md body should be < 100 lines

## Input Format

You will receive a skill proposal:

```json
{
  "name": "pr-reviewer",
  "description": "Review pull requests with a structured checklist",
  "triggers": ["review this PR", "check this pull request", "PR review"],
  "rationale": "User frequently reviews PRs with consistent patterns",
  "allowed_tools": ["Read", "Grep", "Glob", "Bash"],
  "suggested_references": ["prompts/review_checklist.md"],
  "complexity": "moderate"
}
```

## Output Format

Return valid JSON with the scaffolded files:

```json
{
  "skill_md": "---\nname: pr-reviewer\ndescription: |\n  ...\nallowed-tools:\n  - Read\n  ...\n---\n\n# PR Reviewer\n\n...",
  "reference_files": {
    "reference.md": "# PR Reviewer Reference\n\n...",
    "prompts/review_checklist.md": "# PR Review Checklist\n\n..."
  }
}
```

## SKILL.md Structure

### YAML Frontmatter

```yaml
---
name: skill-name
description: |
  One-line description of what the skill does. Include trigger phrases:
  - "trigger phrase one"
  - "trigger phrase two"
  - "trigger phrase three"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---
```

### Body Structure

```markdown
# Skill Title

Brief description of what this skill does and when to use it.

## Outputs

What artifacts this skill produces (files, reports, etc.)

## Workflow

1. Step one
2. Step two
3. Step three

## Examples

### Example 1: Basic usage
Description of a simple use case.

### Example 2: Advanced usage
Description of a more complex use case.

See `reference.md` for implementation details.
```

## Reference File Guidelines

### reference.md
Technical reference with:
- Detailed workflow steps
- File locations and formats
- Edge cases and error handling
- Integration with other systems

### prompts/*.md
LLM prompt templates for:
- Analysis tasks
- Generation tasks
- Transformation tasks

### schemas/*.json
JSON schemas for:
- Input validation
- Output structure
- Configuration

## Tool Scoping

Be conservative with allowed-tools:

| Access Level | Tools | Use Case |
|--------------|-------|----------|
| Read-only | Read, Grep, Glob | Analysis, inspection |
| Safe execute | + Bash | Running tests, linting |
| Modify | + Write, Edit | Code changes |
| Full | + WebFetch, Task | External resources |

Only include tools the skill actually needs.

## Description Guidelines

The description field is critical for skill discovery. Include:

1. **What it does**: One clear sentence
2. **Trigger phrases**: Explicit phrases users might say
3. **Context**: When this skill is useful

Example:
```yaml
description: |
  Review pull requests with a structured checklist covering code quality,
  tests, types, and security. Use when you hear:
  - "review this PR"
  - "check this pull request"
  - "PR review checklist"
  - "what should I look for in this PR"
```

## Important

- Return ONLY valid JSON, no markdown or explanation
- SKILL.md body should be < 100 lines
- Reference external files for detailed instructions
- Use clear, actionable language
- Include practical examples
- Don't over-engineer simple skills
