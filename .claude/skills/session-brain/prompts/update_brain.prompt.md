# Update Brain Prompt

You are updating the Session Brain for a coding project. Given the current brain state and session transcript, produce an updated brain JSON.

## Instructions

1. **Preserve continuity**: Build on existing brain state, don't discard useful context
2. **Extract signal**: Identify goals, decisions, progress, and open questions from the transcript
3. **Be concise**: Summaries should be brief but actionable
4. **Stay factual**: Only record what actually happened, don't speculate
5. **Merge carefully**: Combine new info with existing state, resolving conflicts in favor of newer info

## Input Format

You will receive:

### Current Brain
The existing brain.json (may be empty for first session)

### Session Transcript
A JSONL transcript of the session with user messages, assistant responses, and tool calls.

### Repo Snapshot
Optional repo context (git status, file structure)

## Output Format

Return valid JSON matching the brain schema:

```json
{
  "version": 1,
  "project": {
    "summary": "Brief project description",
    "stack_guesses": ["tech", "stack", "items"],
    "key_commands": ["common", "dev", "commands"]
  },
  "working_set": {
    "current_goal": "What we're working on",
    "current_plan": ["Step 1", "Step 2"],
    "open_questions": ["Unresolved questions"],
    "risks": ["Known blockers or risks"]
  },
  "decisions": [
    {
      "when": "2024-01-15T10:30:00Z",
      "decision": "What was decided",
      "rationale": "Why",
      "implications": ["What it affects"]
    }
  ],
  "progress": {
    "recent_changes": ["What was modified"],
    "done": ["Completed milestones"]
  },
  "signals": {
    "last_session_id": "session-id-here",
    "last_updated_at": "2024-01-15T10:30:00Z"
  }
}
```

## Guidelines

### Project Section
- Update `summary` only if this is the first session or understanding changed significantly
- Add to `stack_guesses` when new technologies are discovered
- Add to `key_commands` when dev commands are used successfully

### Working Set Section
- `current_goal`: What's the active objective? Clear this if goal was completed
- `current_plan`: What are the next steps? Update based on progress
- `open_questions`: What needs clarification? Remove answered questions
- `risks`: What could block progress? Remove resolved risks

### Decisions Section
- Add new decisions when architectural/design choices are made
- Preserve all existing decisions (they form project history)
- Include rationale when available

### Progress Section
- `recent_changes`: Keep only last 1-2 sessions worth (5-10 items max)
- `done`: Major completed milestones only, not every small task

### Signals Section
- Always update `last_session_id` with the current session ID
- Always update `last_updated_at` with current ISO timestamp

## Important

- Return ONLY valid JSON, no markdown or explanation
- If transcript is empty/unclear, make minimal updates (just signals)
- Preserve existing brain content when no new information contradicts it
