# Curriculum Planner Reference

Technical reference for the curriculum planning system.

## State Files

| File | Purpose |
|------|---------|
| `.claude/voyager/curriculum.json` | Structured task backlog |
| `.claude/voyager/curriculum.md` | Human-readable plan |
| `.claude/voyager/brain.json` | Input: project context |

## How Planning Works

1. **Input gathering**
   - Load `brain.json` for project context (goals, decisions, progress)
   - Generate fresh repo snapshot (git status, files, run hints)

2. **LLM planning**
   - Invoke Claude with `plan_curriculum.prompt.md`
   - LLM analyzes context and generates structured tasks
   - Output validated against `curriculum.schema.json`

3. **Output generation**
   - Write `curriculum.json` with full task structure
   - Render `curriculum.md` for human review

## Customizing Plans

### Setting a Goal

The planner infers goals from `brain.json`. To influence the plan:

1. Update `brain.json` → `working_set.current_goal`
2. Re-run the planner

### Track Selection

Tracks are auto-generated based on task types. Common tracks:
- `feature` - New functionality
- `testing` - Test coverage
- `docs` - Documentation
- `infra` - Build/CI/deployment
- `refactor` - Code quality

### Task Scope

Scope levels map roughly to:
- `trivial`: Minutes
- `small`: Hours
- `medium`: Day
- `large`: Days+

## CLI Usage

```bash
# Basic planning
voyager curriculum plan

# With custom inputs
voyager curriculum plan \
  --brain path/to/brain.json \
  --snapshot path/to/snapshot.json

# Dry run (print without saving)
voyager curriculum plan --dry-run

# Skip LLM (just render existing)
voyager curriculum plan --skip-llm
```

## Schema Reference

### Task Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (e.g., `t01`) |
| `title` | Yes | Short action-oriented title |
| `why` | Yes | Rationale for the task |
| `estimated_scope` | Yes | `trivial`/`small`/`medium`/`large` |
| `acceptance_criteria` | Yes | List of verifiable outcomes |
| `suggested_files` | No | Relevant file paths |
| `commands_to_run` | No | Verification commands |
| `depends_on` | No | IDs of prerequisite tasks |
| `status` | No | `pending`/`in_progress`/`done`/`blocked` |

### Metadata Fields

| Field | Description |
|-------|-------------|
| `created_at` | When plan was generated |
| `updated_at` | Last modification time |
| `source_brain_session` | Brain session used as input |
| `total_tasks` | Task count across all tracks |

## Integration with Brain

The curriculum planner reads from brain but doesn't write to it. To update brain based on curriculum progress:

1. Complete tasks and update `curriculum.json` status
2. Run brain update with transcript of work done
3. Brain will incorporate progress into `progress.done`

## Debugging

Check `.claude/voyager/curriculum_last_update.json` for:
- Last run timestamp
- Success/failure status
- Error messages (if any)
- Input file paths used
