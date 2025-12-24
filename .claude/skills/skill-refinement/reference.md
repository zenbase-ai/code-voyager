# Skill Refinement Technical Reference

## Architecture

```
PostToolUse Event
       │
       ▼
┌──────────────────────────────────────┐
│     PostToolUse Hook Script          │
│  .claude/hooks/post_tool_use_feedback.py │
│                                      │
│  • Parses hook input from stdin      │
│  • Determines success/error status   │
│  • Detects skill (lightweight)       │
│  • Logs to SQLite                    │
│  (fast, < 5 second timeout)          │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│        Skill Detector                │
│  src/voyager/refinement/detector.py  │
│                                      │
│  Attribution Cascade:                │
│  1. Transcript (check SKILL.md read) │
│  2. Learned associations             │
│  3. ColBERT index query              │
│  4. LLM inference (disabled in hook) │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│        Feedback Store                │
│  src/voyager/refinement/store.py     │
│                                      │
│  SQLite at .claude/voyager/feedback.db │
│  Tables:                             │
│  • tool_executions                   │
│  • session_summaries                 │
│  • learned_associations              │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│        Insights Generator            │
│  src/voyager/scripts/feedback/insights.py │
│                                      │
│  Aggregates:                         │
│  • Error hotspots per skill          │
│  • Slow/failing workflows            │
│  • Improvement recommendations       │
└──────────────────────────────────────┘
```

## Module Reference

### `voyager.refinement.store`

**`FeedbackStore(db_path=None)`**
SQLite-backed feedback storage. Default path: `.claude/voyager/feedback.db`

Methods:
- `log_tool_execution(execution: ToolExecution)` - Log a tool execution
- `log_session_summary(summary: SessionSummary)` - Log session summary
- `get_session_executions(session_id: str)` - Get all executions for a session
- `get_skill_stats(skill_id=None)` - Get performance stats by skill
- `get_common_errors(skill_id=None, limit=5)` - Get common errors
- `get_tool_usage_stats()` - Get tool usage statistics
- `get_learned_association(context_key)` - Look up learned skill association
- `learn_association(context_key, skill_id, confidence=1.0)` - Store association
- `get_all_learned_associations()` - Get all learned associations
- `get_recent_sessions(limit=10)` - Get recent session summaries
- `get_total_counts()` - Get total executions/sessions/skills counts
- `reset()` - Delete all data

**`ToolExecution`** (dataclass)
- `session_id: str`
- `tool_name: str`
- `tool_input: dict`
- `tool_response: dict | None`
- `success: bool`
- `error_message: str | None`
- `duration_ms: int | None`
- `skill_used: str | None`
- `timestamp: str`

**`SessionSummary`** (dataclass)
- `session_id: str`
- `prompt: str`
- `tools_used: list[str]`
- `skills_detected: list[str]`
- `total_tool_calls: int`
- `successful_calls: int`
- `failed_calls: int`
- `task_completed: bool`
- `completion_feedback: str | None`
- `timestamp: str`

### `voyager.refinement.detector`

**`SkillDetector(db_path=None, use_llm=True, llm_timeout=30)`**
Semantic skill detection using cascade of strategies.

Methods:
- `detect(tool_name, tool_input, transcript_path=None, session_context=None)` - Detect skill

Detection strategies (in order):
1. Check transcript for SKILL.md reads
2. Look up learned associations
3. Query ColBERT index (if `find-skill` available)
4. LLM inference (if `use_llm=True`)

## Database Schema

### tool_executions

```sql
CREATE TABLE tool_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_input TEXT,  -- JSON
    tool_response TEXT,  -- JSON
    success BOOLEAN NOT NULL,
    error_message TEXT,
    duration_ms INTEGER,
    skill_used TEXT,
    timestamp TEXT NOT NULL
);
```

Indexes:
- `idx_tool_executions_skill` on `skill_used`
- `idx_tool_executions_session` on `session_id`
- `idx_tool_executions_tool` on `tool_name`
- `idx_tool_executions_success` on `success`

### session_summaries

```sql
CREATE TABLE session_summaries (
    session_id TEXT PRIMARY KEY,
    prompt TEXT,
    tools_used TEXT,  -- JSON array
    skills_detected TEXT,  -- JSON array
    total_tool_calls INTEGER,
    successful_calls INTEGER,
    failed_calls INTEGER,
    task_completed BOOLEAN,
    completion_feedback TEXT,
    timestamp TEXT NOT NULL
);
```

### learned_associations

```sql
CREATE TABLE learned_associations (
    context_key TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    hit_count INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Context key format: `{tool_name}|{file_extension}|{command_prefix}`

Examples:
- `Write|.py|` - Writing Python files
- `Bash||git commit` - Git commit commands
- `Edit|.md|` - Editing markdown files

## Hook Script Details

The PostToolUse hook (`post_tool_use_feedback.py`) is designed to be:

1. **Fast** - Uses lightweight detection (no LLM by default)
2. **Robust** - Catches all exceptions, never blocks the dev loop
3. **Minimal** - Only logs raw data, defers analysis to insights CLI

Hook input fields used:
- `session_id` - Session identifier
- `tool_name` - Name of the tool (Write, Bash, Edit, etc.)
- `tool_input` - Tool parameters
- `tool_response` - Tool output/result
- `transcript_path` - Path to session transcript

Error detection heuristics:
- Check `tool_response.error` for explicit errors
- Check `tool_response.exit_code != 0` for shell failures
- Check stderr presence with non-zero exit code

## Environment Variables

- `VOYAGER_FEEDBACK_HOOK_ACTIVE` - Set by hook to prevent recursion
- `CLAUDE_PROJECT_DIR` - Project directory (for default paths)

## Files Created

After `voyager feedback setup`:

```
.claude/
├── voyager/
│   └── feedback.db          # SQLite database
├── hooks/
│   └── post_tool_use_feedback.py  # Hook script
└── settings.local.json      # Updated with hook config
```

## Troubleshooting

### No feedback data

1. Check hook is installed: `cat .claude/settings.local.json`
2. Check hook script exists: `ls .claude/hooks/post_tool_use_feedback.py`
3. Try running feedback-setup again

### Hook timeout errors

The hook has a 5-second timeout. If you see timeout errors:
1. Check database isn't locked
2. Consider increasing timeout in settings

### Skill attribution not working

The cascade tries strategies in order. Check:
1. Is a SKILL.md being read in the session?
2. Are learned associations populated?
3. Is `find-skill` available (for ColBERT)?

### Debug mode

Set environment variable for verbose logging:
```bash
VOYAGER_LOG_LEVEL=DEBUG voyager feedback insights
```
