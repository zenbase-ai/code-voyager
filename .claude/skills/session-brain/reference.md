# Session Brain Reference

Technical reference for how Session Brain stores and updates state.

## State Files

All state is stored under `.claude/voyager/` in the project directory:

| File | Purpose |
|------|---------|
| `brain.json` | Canonical structured state (validated against schema) |
| `brain.md` | Human-readable summary for context injection |
| `episodes/<timestamp>_<session_id>.json` | Per-session summaries |
| `brain.last_update.json` | Debug info about last update |

## Schema

See `schemas/brain.schema.json` for the full JSON schema.

### Key Sections

**project** — Stable project understanding (rarely changes)
- `summary`: What this project is
- `stack_guesses`: Inferred tech stack
- `key_commands`: Dev commands that work

**working_set** — Current session context (changes often)
- `current_goal`: Active objective
- `current_plan`: Steps toward goal
- `open_questions`: Unresolved questions
- `risks`: Known blockers

**decisions** — Append-only decision log
- When, what, why, and implications

**progress** — Work tracking
- `recent_changes`: Last 1-2 sessions
- `done`: Major milestones

**signals** — Metadata
- `last_session_id`, `last_updated_at`

## Update Flow

Brain updates happen automatically via hooks:

1. **SessionEnd** / **PreCompact** hook fires
2. Hook script calls `voyager brain update`
3. Script reads transcript + current brain
4. LLM processes changes via `prompts/update_brain.prompt.md`
5. New brain.json is validated and written
6. brain.md is rendered from brain.json
7. Episode file is created for this session

## Manual Operations

### Reading Brain State

To check current brain state:
```bash
cat .claude/voyager/brain.json | jq .
```

Or read brain.md for human-friendly format.

### Recording a Decision

When you want to explicitly record a decision:

1. Say "remember this decision: ..."
2. Or add directly to brain.json decisions array

### Resetting Brain

To start fresh:
```bash
rm -rf .claude/voyager/brain.json .claude/voyager/brain.md
```

The next session will create a new brain from scratch.

### Viewing History

Episode files in `.claude/voyager/episodes/` capture per-session state.
Browse them to see how the brain evolved:
```bash
ls -la .claude/voyager/episodes/
```

## Graceful Degradation

The brain system is designed to never crash hooks:

- Missing brain.json → starts fresh
- Invalid brain.json → backs up and starts fresh
- LLM call fails → writes minimal update note
- Transcript missing → records "no transcript" in episode

## Integration with Other Skills

- **Curriculum Planner**: Reads brain.json to understand project context
- **Skill Factory**: Reads brain + transcript to identify patterns
- **Context Injection**: Reads brain.md for SessionStart injection
