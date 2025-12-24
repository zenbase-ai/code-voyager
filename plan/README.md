# Voyager Plan: Implement 5 Skills (Plugin + Python CLIs)

This plan implements the five “Voyager for Code” capabilities described in `docs/` as a **Claude Code plugin** plus a small **Python package** that provides reusable libraries and installable CLIs.

## Dogfooding principle (this repo is the testbed)

Every capability must be verifiable *inside this repository* (not only in downstream repos):

- **Local state** lives at `./.claude/voyager/` so artifacts are inspectable and diffable.
- **Skills** ship under plugin `skills/`, and are also exposed via a project-local “standalone mirror” under `./.claude/skills/local/` for development (populated by a sync helper).
- **Hooks** are dogfooded two ways:
  - **Real runtime**: via Claude Code hooks when enabled.
  - **Simulation**: by piping fixture JSON into hook scripts (fast + deterministic).
- **Retrieval** must index/search this repo’s own skills (`./skills/**/SKILL.md`), the local mirror (`./.claude/skills/local/**/SKILL.md`), and generated skills (`./.claude/skills/generated/**/SKILL.md`).

## The 5 skills (from `docs/`)

1. **Session Brain**: persistent per-repo working memory under `.claude/voyager/` (`docs/voyager.md`).
2. **Repo Curriculum Planner**: LLM-driven learning/roadmap plan from snapshot + brain (`docs/voyager.md`).
3. **Skill Factory**: propose + scaffold new skills from transcripts/brain (`docs/voyager.md`).
4. **Skill Retrieval System**: ColBERT (RAGatouille) index + semantic search over skills (`docs/retrieval.md`).
5. **Feedback-Driven Skill Refinement**: collect tool outcomes, attribute to skills, surface insights (`docs/refinement.md`).

Skill folder names (to keep the repo internally consistent):

- `skills/session-brain/`
- `skills/curriculum-planner/`
- `skills/skill-factory/`
- `skills/skill-retrieval/`
- `skills/skill-refinement/`

## Repo shape (target)

- `.claude-plugin/plugin.json` (plugin manifest)
- `hooks/hooks.json` (plugin hook wiring)
- `skills/` (five skill folders, each with `SKILL.md` + references/prompts/schemas)
- `scripts/` (hook helpers + deterministic orchestration)
- `src/voyager/` (Python library used by scripts + CLIs)
- `commands/` (optional slash-command prompts for discoverability)
- `.claude/` (dogfooding harness, committed)
  - `.claude/voyager/` (runtime artifacts; gitignored, but created locally for dogfooding)
  - `.claude/hooks/` (standalone hooks for dogfooding without plugin install)
  - `.claude/skills/local/` (runtime mirror of plugin skills; gitignored, populated by a sync helper)
  - `.claude/skills/generated/` (runtime artifacts; gitignored, but created locally for dogfooding)
  - `.claude/fixtures/` (committed: sample transcripts + hook event JSON inputs)
  - `.claude/settings.local.json` (committed: project-local configuration for dogfooding; avoid user/global changes)

## Canonical paths (pick once; keep consistent)

- Project state root: `${CLAUDE_PROJECT_DIR}/.claude/voyager/` (dogfood path: `./.claude/voyager/`)
- Local skill mirror root (dogfood): `${CLAUDE_PROJECT_DIR}/.claude/skills/local/`
- Generated skills root: `${CLAUDE_PROJECT_DIR}/.claude/skills/generated/` (dogfood path: `./.claude/skills/generated/`)
- Generated skills index: `${CLAUDE_PROJECT_DIR}/.claude/voyager/generated_skills_index.json`
- Retrieval index default: `~/.skill-index/` (support override for dogfooding)

## Execution order

Complete tasks sequentially; each task file contains deliverables + acceptance criteria.

- Task 1: `plan/tasks/1.md`
- Task 2: `plan/tasks/2.md`
- Task 3: `plan/tasks/3.md`
- Task 4: `plan/tasks/4.md`
- Task 5: `plan/tasks/5.md`
- Task 6: `plan/tasks/6.md`
- Task 7: `plan/tasks/7.md`
- Task 8: `plan/tasks/8.md`
- Task 9: `plan/tasks/9.md`
- Task 10: `plan/tasks/10.md`
- Task 11: `plan/tasks/11.md`
- Task 12: `plan/tasks/12.md`
- Task 13: `plan/tasks/13.md`
- Task 14: `plan/tasks/14.md`

## Definition of done (high-level)

- Plugin loads and exposes 5 skills, each with clear description triggers + progressive disclosure.
- Session Brain hooks reliably write `.claude/voyager/brain.json` + `brain.md` + episode entries and inject concise context at SessionStart.
- Curriculum Planner produces `.claude/voyager/curriculum.json` + `curriculum.md` with acceptance criteria + verification commands.
- Skill Factory scaffolds new skills into `.claude/skills/generated/<name>/` without overwriting existing skills.
- Retrieval CLIs (`skill-index`, `find-skill`) work on any skill library with auto-discovery and store an index persistently.
- Refinement collects PostToolUse feedback (SQLite) with semantic skill attribution and surfaces `skill-insights` output.
- Dogfooding works end-to-end in this repo via fixture-driven hook simulation plus (optionally) enabling real hooks.
