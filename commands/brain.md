---
name: brain
description: Show, update, or query the Session Brain
---

Use the **session-brain** skill to help the user with their request.

Common operations:

- **Show current state**: Read `.claude/voyager/brain.md` and summarize it
- **What's next?**: Check `brain.json` → `working_set.current_plan` and suggest next step
- **Record a decision**: Add to `brain.json` → `decisions` array with timestamp, decision, rationale
- **Answer context questions**: Use brain.json to answer "what were we doing?", "why did we choose X?", etc.

If no specific request is given, show the current brain state summary.
