Below is a single “agent instruction” file you can drop in as CLAUDE.md (or rename to AGENTS.md) that directs a coding agent to build a clean, generalizable repo implementing the three Skills: Session Brain, Repo Curriculum Planner, and Skill Factory, using Claude Code Skills + hooks and LLM-driven behavior (not a pile of hard-coded logic).

This design leans on:
	•	Skills as “progressive disclosure” instruction folders with optional scripts/resources, and allowed-tools scoping.  ￼
	•	Hooks to ingest transcript_path/session_id, run project/plugin scripts, and inject context at SessionStart.  ￼
	•	claude -p programmatic mode to run a small LLM sub-call from scripts and return structured JSON.  ￼
	•	Plugins as the most reusable packaging for team + multi-repo use (vs .claude/ standalone).  ￼

# Code Voyager: Session Brain + Repo Curriculum Planner + Skill Factory

You are implementing a repository that ships **three Claude Code Skills** (Session Brain, Repo Curriculum Planner, Skill Factory) plus the **hooks + scripts** needed to make them feel “native” and largely automatic.

---

## 0) Non-negotiables

### Product goals
- **Elegant**: minimal moving parts, composable pieces, small surface area.
- **Generalizable**: works across languages and repo types; no framework-specific assumptions.
- **LLM-driven**: use the LLM for interpretation, planning, and extraction; keep scripts mostly for I/O, formatting, state, and orchestration.
- **Programmer-first**: optimize for real dev loops (debugging, onboarding, refactors, test failures, PR prep, “what next?”).

### Claude Code constraints (design around these)
- Skills should be discoverable by description triggers; keep them focused and readable.
- Use **progressive disclosure**: keep `SKILL.md` short and point to other files/scripts. (Aim: SKILL.md body < ~500 lines.)
- Hooks can read `transcript_path` and run scripts at lifecycle events; `SessionStart` can inject additional context.
- `claude -p` can be invoked programmatically; use `--output-format json` when you need structured results.

---

## 1) Repo form factor

Implement as a **Claude Code plugin** (most reusable), with optional “standalone” `.claude/` mirror for easy local testing.

### Required plugin structure
At repo root:

- `.claude-plugin/plugin.json`
- `skills/`
- `hooks/hooks.json`
- `scripts/` (helper code for hooks + skills)
- `commands/` (optional but recommended for discoverability)

Keep everything self-contained inside the repo (plugins are cached/copied when installed, so don’t reference `../`).

---

## 2) Deliverables (what to build)

### A) Plugin manifest
Create: `.claude-plugin/plugin.json`

- Name: something like `Code Voyager` (hyphenated, stable).
- Version: `0.1.0` initially.
- Description: “Persistent session memory + repo curriculum planning + self-generating skills for Claude Code.”

### B) Three Skills (plugin Skills)
Under `skills/` create:

1. `skills/session-brain/SKILL.md`
2. `skills/curriculum-planner/SKILL.md`
3. `skills/skill-factory/SKILL.md`

Each must:
- Include YAML frontmatter: `name`, `description`, and `allowed-tools` (tight by default).
- Have a description that includes **explicit triggers** (phrases users will actually say).
- Use progressive disclosure: reference `reference.md`, `schemas/*.json`, and scripts rather than embedding everything.

### C) Hooks that make Session Brain “just work”
Create: `hooks/hooks.json` with hooks for:
- `SessionStart` → inject “brain context” and current repo state
- `PreCompact` → persist memory before compaction
- `SessionEnd` → persist memory when session ends

Hooks should call plugin scripts via `${CLAUDE_PLUGIN_ROOT}` and write/read state under `${CLAUDE_PROJECT_DIR}/.claude/voyager/`.

### D) CLI and Script library

**Unified CLI** (`voyager`):
- `voyager brain update` — LLM-updates the brain from transcript + repo snapshot
- `voyager brain inject` — prints JSON hook output injecting brain summary + snapshot
- `voyager repo snapshot` — cheap, language-agnostic repo snapshot (git status/log + tree stats)
- `voyager curriculum plan` — LLM produces a curriculum plan artifact from snapshot + brain
- `voyager factory propose` — LLM mines transcript/brain to propose new skills
- `voyager factory scaffold` — scaffolds a new skill into `.claude/skills/generated/<name>/…`
- `voyager factory list` — list available skill proposals

**Hook scripts** (called by hooks.json):
- `scripts/hooks/session_start.py` — SessionStart hook handler
- `scripts/hooks/pre_compact.py` — PreCompact hook handler
- `scripts/hooks/session_end.py` — SessionEnd hook handler

**Library modules** (under `src/voyager/`):
- `voyager.llm` — wrapper for Claude Agent SDK calls
- `voyager.io` — safe read/write helpers, atomic writes
- `voyager.brain.render` — deterministic renderer from JSON → Markdown snippet for context injection

All scripts must be:
- Fast enough for hooks (timeouts: 5–20s).
- Defensive (missing git, missing files, no previous memory).
- Cross-platform-ish (macOS/Linux). (Windows optional.)

---

## 3) Shared state model (the “Brain Store”)

All three Skills share a single state directory in the *project*:

`${CLAUDE_PROJECT_DIR}/.claude/voyager/`

Structure:

- `.claude/voyager/brain.json`
  Canonical structured state (versioned schema).

- `.claude/voyager/brain.md`
  Rendered, human-friendly summary.

- `.claude/voyager/curriculum.json`
  Latest plan and backlog with metadata.

- `.claude/voyager/episodes/`
  One file per session/compaction summarizing progress.

- `.claude/voyager/generated-skills/`
  Output location for Skill Factory scaffolds (or use `.claude/skills/generated/` — choose one and be consistent).

### brain.json schema (v1)
Define a JSON schema file in `skills/session-brain/schemas/brain.schema.json` and keep the JSON itself in:

```json
{
  "version": 1,
  "project": {
    "summary": "",
    "stack_guesses": [],
    "key_commands": []
  },
  "working_set": {
    "current_goal": "",
    "current_plan": [],
    "open_questions": [],
    "risks": []
  },
  "decisions": [
    { "when": "", "decision": "", "rationale": "", "implications": [] }
  ],
  "progress": {
    "recent_changes": [],
    "done": []
  },
  "signals": {
    "last_session_id": "",
    "last_updated_at": ""
  }
}

Do not hardcode repo-specific content. The LLM should update fields based on transcript and lightweight repo snapshot.

⸻

4) Hooks implementation details

Hook philosophy

Hooks should:
	•	Gather minimal, high-signal data
	•	Call the LLM only when needed
	•	Write stable artifacts to .claude/voyager/
	•	Inject only a concise, actionable context block (no walls of text)

Recursion guard (critical)

Because hooks will call claude -p, prevent infinite recursion:
	•	When calling claude -p from any script, set an env var like:
	•	VOYAGER_FOR_CODE_INTERNAL=1
	•	At the top of every hook script: if VOYAGER_FOR_CODE_INTERNAL=1, exit 0 immediately.

This ensures claude -p runs don’t trigger your plugin hooks in a loop.

hooks/hooks.json (design)

Implement hooks that call:
	1.	SessionStart → `scripts/hooks/session_start.py` (calls `voyager brain inject`)

	•	Reads .claude/voyager/brain.md (if exists) and a fresh repo snapshot.
	•	Outputs JSON with hookSpecificOutput.additionalContext containing:
	•	"Session Brain (compressed)"
	•	"Repo Snapshot (compressed)"
	•	"Top 3 next actions" if available

	2.	PreCompact → `scripts/hooks/pre_compact.py` (calls `voyager brain update`)

	•	Uses transcript_path to summarize what happened and update brain.json
	•	Writes an episode entry
	•	Updates brain.md

	3.	SessionEnd → `scripts/hooks/session_end.py` (calls `voyager brain update`)

	•	Same as PreCompact but with reason metadata stored

Hook input + output handling
	•	Parse stdin JSON to get session_id, transcript_path, cwd, hook_event_name, etc.
	•	For SessionStart injection: print valid JSON to stdout:

{ "hookSpecificOutput": { "additionalContext": "..." }, "suppressOutput": true }



⸻

5) claude -p integration (LLM engine)

Implement scripts/lib/claude_print.py:
	•	Runs: claude -p "<prompt>" --output-format json
	•	Optionally append a short system instruction that the sub-call must:
	•	NOT use tools
	•	ONLY output valid JSON for the schema you request
	•	Parse stdout JSON and return .result (string) and/or .session_id.

Use this for:
	•	Updating brain.json
	•	Producing curriculum plans
	•	Proposing/scaffolding skills

If claude isn’t available, fail gracefully:
	•	Don’t crash hooks
	•	Write a minimal fallback brain.md that says memory update skipped.

⸻

6) Skill 1: Session Brain

Purpose

Persistent “working memory” for coding sessions:
	•	What we’re doing
	•	Why we’re doing it
	•	What changed
	•	What’s next
	•	Decisions + rationales
	•	Open questions + risks

Folder contents

skills/session-brain/:
	•	SKILL.md
	•	reference.md (how state works, how to pin decisions, how to reset)
	•	schemas/brain.schema.json
	•	prompts/update_brain.prompt.md (the LLM prompt template)
	•	(Optional) examples.md

allowed-tools

Default to safe tools:
	•	Read, Grep, Glob, Bash
(Do not include Write by default; the hooks/scripts do the writing. If you add Write, be explicit.)

SKILL.md must teach Claude:
	•	Where brain files live (.claude/voyager/…)
	•	How to interpret and update them when explicitly asked
	•	How to use the brain to answer “resume”, “what’s next”, “remind me”, “why did we choose X”
	•	How to record decisions in a structured way

User-facing triggers (put in description)

Examples:
	•	“resume where we left off”
	•	“what were we doing?”
	•	“recap this repo”
	•	“remember this decision”
	•	“save this as a project rule”
	•	“what’s next?”

⸻

7) Skill 2: Repo Curriculum Planner

Purpose

Voyager-style curriculum, but for real repos:
	•	Generate a sequence of high-leverage tasks that increase understanding and improve the codebase
	•	Calibrate difficulty: small wins → deeper work
	•	Produce “next best action” plans that are testable

Inputs
	•	.claude/voyager/brain.json
	•	repo snapshot (git status/log, directory summary)
	•	optionally: the user’s stated goal (“ship feature X”, “stabilize tests”, “onboard me”)

Outputs
	•	.claude/voyager/curriculum.json with:
	•	goal
	•	tracks (e.g., “onboarding”, “stability”, “performance”, “security”, “DX”)
	•	tasks: each task has why, estimated_scope, acceptance_criteria, suggested_files, commands_to_run
	•	.claude/voyager/curriculum.md rendered for humans

LLM-driven, not hardcoded

Do not implement language-specific planners.
Instead:
	•	Snapshot is generic.
	•	LLM infers stack + highest ROI tasks.
	•	Tasks must include acceptance criteria and commands to verify.

allowed-tools

This skill is allowed to inspect and plan:
	•	Read, Grep, Glob, Bash
Optionally allow Write only when user asks to materialize the plan into files.

Triggers

Examples:
	•	“what should I work on next?”
	•	“make an onboarding plan”
	•	“create a learning path for this repo”
	•	“prioritize improvements”
	•	“roadmap this refactor”

⸻

8) Skill 3: Skill Factory

Purpose

Self-improving skill library for programming workflows:
	•	Mine transcripts + brain + curriculum for repeated patterns
	•	Propose new Skills
	•	Scaffold new Skill folders with good descriptions + progressive disclosure
	•	Keep the skill library clean (avoid duplicates)

Workflow (LLM-led)
	1.	Identify repeated workflow patterns:
	•	“review PRs”
	•	“write migration scripts”
	•	“debug flaky tests”
	•	“generate commit messages”
	•	“triage CI failures”
	2.	Turn each into a skill proposal:
	•	name
	•	description with triggers
	•	allowed-tools policy
	•	files/scripts needed
	3.	Scaffold into .claude/skills/generated/<skill-name>/
	4.	Update an index: .claude/voyager/generated_skills_index.json

Guardrails
	•	Never overwrite existing skills without explicit confirmation.
	•	Validate YAML frontmatter.
	•	Keep SKILL.md short and point to references/scripts.
	•	If a generated skill needs code, put it in scripts/ under that skill and reference it.

allowed-tools

This skill needs to write scaffolds:
	•	Read, Grep, Glob, Bash, Write, Edit

Triggers

Examples:
	•	“turn this workflow into a skill”
	•	“make a skill for our PR review process”
	•	“generate a new skill”
	•	“automate this repeated process”

⸻

9) Optional but recommended: Slash commands for ergonomics

Add commands/:
	•	commands/brain.md → “Show brain, update brain, record a decision”
	•	commands/curriculum.md → “Generate / refresh curriculum”
	•	commands/factory.md → “Propose 3 new skills, then scaffold chosen one”

Commands are just prompts; keep them simple and point to the Skills.

⸻

10) Definition of done (acceptance tests)

Functional
	•	Installing/loading plugin makes the 3 Skills available.
	•	On session start, Claude receives injected context summarizing:
	•	last known brain state
	•	current repo snapshot
	•	On pre-compact and session end, brain artifacts are updated:
	•	brain.json valid
	•	brain.md rendered
	•	episode entry created
	•	Repo Curriculum Planner can produce a plan file with acceptance criteria.
	•	Skill Factory can scaffold a new generated skill with valid YAML + references.

Quality
	•	No repo-specific hardcoding.
	•	Scripts are small and reusable; business logic lives in prompts/schemas.
	•	Progressive disclosure: SKILL.md points to references; no mega-files.
	•	Recursion guard works (no infinite hook loops).

Safety
	•	Hooks must never delete files or run destructive commands.
	•	All writes must be confined to:
	•	.claude/voyager/
	•	.claude/skills/generated/ (if used)

⸻

11) Implementation order (do this in sequence)
	1.	Create plugin skeleton + manifest.
	2.	Implement repo snapshot script.
	3.	Implement brain schema + renderer + update script (LLM call).
	4.	Implement hooks (SessionStart inject + PreCompact/SessionEnd update).
	5.	Write Session Brain skill docs that match the behavior.
	6.	Implement curriculum planner (LLM plan → json + md).
	7.	Implement skill factory (propose → scaffold).
	8.	Add optional commands.
	9.	Manual smoke test in a real repo.

⸻

12) Notes on elegance

If you’re tempted to hardcode “if package.json then npm test”: don’t.
Instead:
	•	Snapshot collects a few common signals (git status/log, top-level files, maybe ripgrep for “how to run tests” docs).
	•	The LLM infers the best commands and validates them cautiously.

The scripts are “sensors + actuators”.
The LLM is the “planner + summarizer + librarian”.
