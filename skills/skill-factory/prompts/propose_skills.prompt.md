# Propose Skills Prompt

You are analyzing coding session patterns to propose reusable skills for Claude Code. Given the brain state, transcript, or curriculum, identify repeated workflows that could become skills.

## Instructions

1. **Analyze patterns**: Look for repeated actions, common workflows, or recurring tasks
2. **Extract triggers**: Identify natural language phrases users might say
3. **Determine tools**: What Claude Code tools would this skill need?
4. **Assess value**: Is this pattern frequent/valuable enough to be a skill?

## Input Format

You will receive some combination of:

### Brain State
Current brain.json with project context, decisions, and working patterns.

### Transcript Summary
Summary of recent session transcripts showing common actions.

### Curriculum
Current curriculum showing planned/completed tasks.

## Output Format

Return valid JSON matching the skill_proposal schema:

```json
{
  "version": 1,
  "proposals": [
    {
      "name": "pr-reviewer",
      "description": "Review pull requests with a structured checklist",
      "triggers": [
        "review this PR",
        "check this pull request",
        "PR review"
      ],
      "rationale": "User frequently reviews PRs with a consistent pattern of checking tests, types, and security",
      "allowed_tools": ["Read", "Grep", "Glob", "Bash"],
      "suggested_references": ["prompts/review_checklist.md"],
      "complexity": "moderate",
      "priority": "high"
    }
  ],
  "metadata": {
    "created_at": "2024-01-15T10:30:00Z",
    "source": "brain",
    "total_proposals": 1
  }
}
```

## Good Skill Candidates

Skills work best for:

### Workflow Patterns
- **PR review**: Checking code, tests, types, security concerns
- **Commit preparation**: Staging, writing messages, pre-commit checks
- **Test debugging**: Analyzing failures, fixing flaky tests
- **Migration writing**: Database or code migrations
- **API design**: Endpoint documentation, OpenAPI specs
- **Release management**: Changelog, versioning, tagging

### Repeated Operations
- **Log analysis**: Parsing error logs, identifying patterns
- **Performance profiling**: Running benchmarks, analyzing results
- **Dependency updates**: Checking outdated, updating, testing
- **Code generation**: Scaffolding components, boilerplate

### Domain-Specific Tasks
- **Frontend components**: React/Vue/Svelte patterns
- **API endpoints**: REST/GraphQL patterns
- **Test writing**: Unit, integration, e2e patterns
- **Documentation**: READMEs, API docs, guides

## Skill Naming Guidelines

- Use lowercase with hyphens: `pr-reviewer`, `test-debugger`
- Be specific but not too narrow: `api-endpoint` not `fastapi-post-endpoint`
- Prefer verb-noun: `commit-helper`, `log-analyzer`
- Avoid generic names: not just `helper` or `utils`

## Trigger Guidelines

- Use natural, conversational phrases
- Include variations: "review this PR", "check this PR", "PR review"
- Think about how users actually ask for help
- Include both command-style and question-style triggers

## Tool Selection

Common tool combinations:

| Skill Type | Typical Tools |
|------------|---------------|
| Read-only analysis | Read, Grep, Glob |
| Code inspection | Read, Grep, Glob, Bash |
| Code modification | Read, Grep, Glob, Bash, Write, Edit |
| Full access | Read, Grep, Glob, Bash, Write, Edit, WebFetch |

Be conservative - only include tools the skill actually needs.

## Priority Guidelines

- **high**: Pattern appears frequently (3+ times) and saves significant time
- **medium**: Pattern appears occasionally and provides clear value
- **low**: Pattern is useful but rare or quick to do manually

## Complexity Guidelines

- **simple**: Just instructions in SKILL.md, no additional files
- **moderate**: Needs prompts or reference files
- **complex**: Needs scripts, schemas, or complex logic

## Important

- Return ONLY valid JSON, no markdown or explanation
- Propose 1-5 skills max per session (quality over quantity)
- Skip skills that already exist or are too similar to existing ones
- Focus on patterns that would save time across multiple uses
- Consider the project's tech stack when suggesting domain-specific skills
