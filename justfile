# Justfile – handy task runner (https://just.systems)

# --- settings ---------------------- https://just.systems/man/en/settings.html
set dotenv-load := true
set dotenv-path := ".env"
set ignore-comments := true

fmt:
  uv run ruff check --fix && \
  uv run ruff format

lint:
  uv run ruff check && \
  uv run ruff format --check

test:
  uv run pytest -q

# --- voyager CLI commands ---
snapshot:
  uv run voyager repo snapshot --compact | python -m json.tool

brain-update *ARGS:
  uv run voyager brain update {{ARGS}}

brain-inject:
  uv run voyager brain inject

curriculum-plan *ARGS:
  uv run voyager curriculum plan {{ARGS}}

factory-propose *ARGS:
  uv run voyager factory propose {{ARGS}}

factory-scaffold *ARGS:
  uv run voyager factory scaffold {{ARGS}}

factory-list:
  uv run voyager factory list

# --- dev helpers ---
sync-skills:
  python scripts/dev/sync_skills.py --clean --verbose

# --- hook testing ---
hook-session-start:
  cat .claude/fixtures/hooks/session_start.json | python scripts/hooks/session_start.py | python -m json.tool

hook-pre-compact:
  cat .claude/fixtures/hooks/pre_compact.json | python scripts/hooks/pre_compact.py | python -m json.tool

hook-session-end:
  cat .claude/fixtures/hooks/session_end.json | python scripts/hooks/session_end.py | python -m json.tool
