---
name: curriculum
description: Generate, show, or refresh the curriculum plan
---

Use the **curriculum-planner** skill to help the user with their request.

Common operations:

- **What should I work on next?**: Suggest 2-3 high-priority tasks based on brain + repo state
- **Show current plan**: Read `.claude/voyager/curriculum.md` and summarize it
- **Generate/refresh plan**: Run `voyager curriculum plan` to create new curriculum
- **Preview plan**: Run `voyager curriculum plan --dry-run` to see what would be generated
- **Update task status**: Edit `curriculum.json` to mark tasks as `in_progress` or `done`

Two modes:
1. **Propose in chat** (default): Discuss tasks without writing files
2. **Write to disk**: Only when explicitly asked ("save the plan", "write curriculum")

If no specific request is given, read the current curriculum and suggest the next task.
