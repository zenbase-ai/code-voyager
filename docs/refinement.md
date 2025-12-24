# Feedback-Driven Skill Refinement

## Project Vision

Build a **Voyager-inspired feedback loop** that captures execution outcomes, attributes them to skills semantically, and surfaces improvement insights. This version eliminates manual configuration—skill detection uses **LLM inference** or **Pattern 1's ColBERT index** instead of hardcoded mappings.

> **Design Principle**: The system should work out-of-the-box with ANY skill library. No manual mappings, no configuration files, no domain knowledge required from the user.

---

## What's Different in v2

| v1 (Over-specified) | v2 (Generalized) |
|---------------------|------------------|
| `SKILL_PATTERNS` dictionary | Query ColBERT index OR LLM inference |
| File extension matching | Semantic matching against skill purposes |
| Manual hook JSON editing | `feedback-setup` auto-installs hooks |
| Hardcoded tool→skill maps | Learn associations from execution patterns |

---

## Quick Start

```bash
# Install
pip install -e .

# Auto-setup hooks (one command, no manual JSON editing)
feedback-setup

# Use Claude Code normally - feedback is collected automatically

# View insights
skill-insights
```

That's it. No configuration, no manual mappings.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FEEDBACK COLLECTION (Zero Config)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                            │
│  │  Tool Use   │  (Write, Bash, Edit, etc.)                                │
│  └──────┬──────┘                                                            │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PostToolUse Hook                                  │   │
│  │                                                                      │   │
│  │  Captures: tool_name, tool_input, tool_response, success/error      │   │
│  └─────────────────────────────┬───────────────────────────────────────┘   │
│                                │                                            │
│                                ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 SKILL ATTRIBUTION (Semantic)                         │   │
│  │                                                                      │   │
│  │  Option A: Query Pattern 1's ColBERT index                          │   │
│  │     "What skill handles writing .docx files?"                       │   │
│  │                                                                      │   │
│  │  Option B: LLM inference (if no index available)                    │   │
│  │     "Given this tool usage, which skill was likely used?"           │   │
│  │                                                                      │   │
│  │  Option C: Learn from transcript context                            │   │
│  │     Check if Claude mentioned reading a SKILL.md earlier            │   │
│  └─────────────────────────────┬───────────────────────────────────────┘   │
│                                │                                            │
│                                ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Feedback Store (SQLite)                           │   │
│  │                                                                      │   │
│  │  • Execution logs with attributed skills                            │   │
│  │  • Learned tool→skill associations                                  │   │
│  │  • Error patterns by skill                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Implementation

### 1. Semantic Skill Detector (`skill_detector.py`)

```python
"""
Detect which skill is being used based on tool execution context.

NO HARDCODED MAPPINGS. Uses semantic matching via:
1. ColBERT index query (if Pattern 1 is installed)
2. LLM inference (fallback)
3. Transcript context (check what SKILL.md was read)
4. Learning from past attributions
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
import subprocess

class SkillDetector:
    """
    Semantically detect which skill is being used from tool execution context.
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or (Path.home() / ".feedback" / "feedback.db")
        self._colbert_available = None
        self._learned_associations: Dict[str, str] = {}
        self._load_learned_associations()

    def detect(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        transcript_path: Optional[str] = None,
        session_context: Optional[str] = None
    ) -> Optional[str]:
        """
        Detect which skill is being used.

        Tries multiple strategies in order of preference:
        1. Transcript context (most accurate - Claude explicitly read a skill)
        2. Learned associations (fast, from past sessions)
        3. ColBERT index query (semantic, if available)
        4. LLM inference (slowest, but works for anything)

        Returns:
            skill_id or None if uncertain
        """

        # Strategy 1: Check transcript for explicit skill reading
        if transcript_path:
            skill = self._detect_from_transcript(transcript_path)
            if skill:
                return skill

        # Strategy 2: Check learned associations
        context_key = self._make_context_key(tool_name, tool_input)
        if context_key in self._learned_associations:
            return self._learned_associations[context_key]

        # Strategy 3: Query ColBERT index
        if self._is_colbert_available():
            skill = self._detect_via_colbert(tool_name, tool_input)
            if skill:
                self._learn_association(context_key, skill)
                return skill

        # Strategy 4: LLM inference (expensive but comprehensive)
        skill = self._detect_via_llm(tool_name, tool_input, session_context)
        if skill:
            self._learn_association(context_key, skill)
            return skill

        return None

    def _detect_from_transcript(self, transcript_path: str) -> Optional[str]:
        """
        Check the session transcript for skill file reads.

        If Claude read "/mnt/skills/docx/SKILL.md" earlier in the session,
        we know the docx skill is being used.
        """
        try:
            transcript = Path(transcript_path)
            if not transcript.exists():
                return None

            # Parse JSONL transcript
            skill_reads = []
            for line in transcript.read_text().splitlines():
                try:
                    entry = json.loads(line)
                    # Look for file reads of SKILL.md
                    if entry.get("tool_name") == "Read":
                        path = entry.get("tool_input", {}).get("file_path", "")
                        if "SKILL.md" in path:
                            # Extract skill ID from path
                            # e.g., "/mnt/skills/docx/SKILL.md" -> "docx"
                            parts = Path(path).parts
                            if "skills" in parts:
                                idx = parts.index("skills")
                                if idx + 1 < len(parts) - 1:
                                    skill_reads.append(parts[idx + 1])
                except json.JSONDecodeError:
                    continue

            # Return most recently read skill
            return skill_reads[-1] if skill_reads else None

        except Exception:
            return None

    def _detect_via_colbert(
        self,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> Optional[str]:
        """Query Pattern 1's ColBERT index for skill matching."""
        try:
            # Construct a natural query from tool context
            query = self._tool_context_to_query(tool_name, tool_input)

            # Call the find-skill CLI
            result = subprocess.run(
                ["find-skill", query, "-k", "1", "--json"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                results = json.loads(result.stdout)
                if results and results[0].get("score", 0) > 0.5:
                    return results[0]["skill_id"]

            return None

        except Exception:
            return None

    def _detect_via_llm(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        session_context: Optional[str] = None
    ) -> Optional[str]:
        """Use LLM to infer which skill is being used."""
        try:
            prompt = self._build_detection_prompt(tool_name, tool_input, session_context)

            # Try available LLM
            result = subprocess.run(
                self._get_llm_command(prompt),
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                response = result.stdout.strip()
                # Parse skill ID from response
                return self._parse_skill_from_response(response)

            return None

        except Exception:
            return None

    def _tool_context_to_query(
        self,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Convert tool execution context to a natural language query."""
        parts = []

        # File path gives strong signal
        file_path = tool_input.get("file_path", "")
        if file_path:
            ext = Path(file_path).suffix
            if ext:
                parts.append(f"working with {ext} files")

        # Command content for Bash
        command = tool_input.get("command", "")
        if command:
            # Extract key terms from command
            if "python" in command.lower():
                parts.append("python script")
            # Look for library names
            for lib in ["docx", "pdf", "xlsx", "pptx", "pandas", "openpyxl"]:
                if lib in command.lower():
                    parts.append(f"using {lib}")

        # Tool name context
        tool_descriptions = {
            "Write": "creating or writing files",
            "Edit": "editing existing files",
            "Bash": "running commands",
            "Read": "reading file contents"
        }
        if tool_name in tool_descriptions:
            parts.append(tool_descriptions[tool_name])

        return " ".join(parts) if parts else f"using {tool_name} tool"

    def _build_detection_prompt(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        session_context: Optional[str]
    ) -> str:
        """Build prompt for LLM skill detection."""
        return f'''Given this Claude Code tool execution, identify which skill is likely being used.

Tool: {tool_name}
Input: {json.dumps(tool_input, indent=2)[:1000]}
{f"Session context: {session_context[:500]}" if session_context else ""}

Common Claude Skills include: docx, pdf, xlsx, pptx, and custom user skills.

Return ONLY the skill ID (e.g., "docx") or "unknown" if uncertain.
Do not explain, just return the skill ID.'''

    def _get_llm_command(self, prompt: str) -> str:
        """Get command to invoke available LLM."""
        import shutil
        escaped = prompt.replace("'", "'\\''")

        if shutil.which("claude"):
            return f"claude -p '{escaped}' --output-format text"
        if shutil.which("llm"):
            return f"llm '{escaped}'"
        if shutil.which("ollama"):
            return f"ollama run llama3 '{escaped}'"

        raise RuntimeError("No LLM available")

    def _parse_skill_from_response(self, response: str) -> Optional[str]:
        """Extract skill ID from LLM response."""
        response = response.strip().lower()
        if response == "unknown" or not response:
            return None
        # Clean up common response patterns
        response = response.replace('"', '').replace("'", "")
        if response.startswith("skill:"):
            response = response[6:].strip()
        return response if len(response) < 50 else None

    def _make_context_key(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Create a hashable key from tool context for learning."""
        # Use file extension and tool name as key
        file_path = tool_input.get("file_path", "")
        ext = Path(file_path).suffix if file_path else ""
        command = tool_input.get("command", "")[:50]  # First 50 chars of command
        return f"{tool_name}|{ext}|{command}"

    def _learn_association(self, context_key: str, skill_id: str):
        """Learn a tool context → skill association."""
        self._learned_associations[context_key] = skill_id
        self._save_learned_associations()

    def _load_learned_associations(self):
        """Load learned associations from database."""
        try:
            if not self.db_path.exists():
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT context_key, skill_id FROM learned_associations
            """)

            for row in cursor.fetchall():
                self._learned_associations[row[0]] = row[1]

            conn.close()
        except Exception:
            pass

    def _save_learned_associations(self):
        """Save learned associations to database."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learned_associations (
                    context_key TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL
                )
            """)

            for key, skill in self._learned_associations.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO learned_associations (context_key, skill_id)
                    VALUES (?, ?)
                """, (key, skill))

            conn.commit()
            conn.close()
        except Exception:
            pass

    def _is_colbert_available(self) -> bool:
        """Check if Pattern 1's ColBERT index is available."""
        if self._colbert_available is None:
            import shutil
            self._colbert_available = shutil.which("find-skill") is not None
        return self._colbert_available
```

### 2. Auto-Setup Script (`setup.py`)

```python
#!/usr/bin/env python3
"""
Auto-setup feedback collection hooks.

Run: feedback-setup

This automatically:
1. Detects Claude Code settings location
2. Installs hooks without overwriting existing ones
3. Creates necessary directories
4. Validates installation
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any
import sys

def find_settings_file() -> Path:
    """Find Claude Code settings file location."""
    candidates = [
        Path.cwd() / ".claude" / "settings.json",           # Project settings
        Path.cwd() / ".claude" / "settings.local.json",     # Local project settings
        Path.home() / ".claude" / "settings.json",          # User settings
    ]

    for path in candidates:
        if path.exists():
            return path

    # Default to project settings (will create)
    return Path.cwd() / ".claude" / "settings.json"

def get_hooks_dir() -> Path:
    """Get or create hooks directory."""
    hooks_dir = Path.cwd() / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    return hooks_dir

def install_hook_scripts(hooks_dir: Path):
    """Install Python hook scripts."""

    # PostToolUse hook - main feedback collection
    post_tool_script = '''#!/usr/bin/env python3
"""PostToolUse hook - Capture execution feedback."""
import json
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

def main():
    try:
        hook_input = json.load(sys.stdin)
    except:
        sys.exit(0)

    session_id = hook_input.get("session_id", "unknown")
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_response = hook_input.get("tool_response", {})
    transcript_path = hook_input.get("transcript_path")

    success = tool_response.get("success", True)
    error_message = None
    if not success:
        error_message = tool_response.get("error", tool_response.get("stderr", ""))[:500]

    # Detect skill (semantic)
    try:
        from skill_detector import SkillDetector
        detector = SkillDetector()
        skill_used = detector.detect(tool_name, tool_input, transcript_path)
    except:
        skill_used = None

    # Log to store
    try:
        from feedback_store import FeedbackStore, ToolExecution
        store = FeedbackStore()
        store.log_tool_execution(ToolExecution(
            session_id=session_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_response=tool_response,
            success=success,
            error_message=error_message,
            duration_ms=None,
            skill_used=skill_used,
            timestamp=datetime.utcnow().isoformat()
        ))
    except Exception as e:
        print(f"Logging error: {e}", file=sys.stderr)

    sys.exit(0)

if __name__ == "__main__":
    main()
'''

    # Stop hook - session summary
    stop_script = '''#!/usr/bin/env python3
"""Stop hook - Session summary and verification."""
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

def main():
    try:
        hook_input = json.load(sys.stdin)
    except:
        sys.exit(0)

    session_id = hook_input.get("session_id", "unknown")

    # Prevent infinite loops
    if hook_input.get("stop_hook_active"):
        sys.exit(0)

    try:
        from feedback_store import FeedbackStore, SessionSummary
        store = FeedbackStore()
        executions = store.get_session_executions(session_id)

        if not executions:
            sys.exit(0)

        tools_used = list(set(e.tool_name for e in executions))
        skills_detected = list(set(e.skill_used for e in executions if e.skill_used))
        total = len(executions)
        successful = sum(1 for e in executions if e.success)

        store.log_session_summary(SessionSummary(
            session_id=session_id,
            prompt="",
            tools_used=tools_used,
            skills_detected=skills_detected,
            total_tool_calls=total,
            successful_calls=successful,
            failed_calls=total - successful,
            task_completed=successful / total > 0.8 if total > 0 else True,
            completion_feedback=None,
            timestamp=datetime.utcnow().isoformat()
        ))
    except Exception as e:
        print(f"Summary error: {e}", file=sys.stderr)

    sys.exit(0)

if __name__ == "__main__":
    main()
'''

    (hooks_dir / "post_tool_use.py").write_text(post_tool_script)
    (hooks_dir / "stop_hook.py").write_text(stop_script)

    # Make executable
    for script in hooks_dir.glob("*.py"):
        script.chmod(0o755)

def merge_hooks_config(existing: Dict[str, Any]) -> Dict[str, Any]:
    """Merge our hooks with existing config without overwriting."""
    hooks_dir = get_hooks_dir()

    our_hooks = {
        "PostToolUse": [{
            "matcher": "*",
            "hooks": [{
                "type": "command",
                "command": f"python3 \"{hooks_dir}/post_tool_use.py\"",
                "timeout": 5
            }]
        }],
        "Stop": [{
            "matcher": "",
            "hooks": [{
                "type": "command",
                "command": f"python3 \"{hooks_dir}/stop_hook.py\"",
                "timeout": 10
            }]
        }]
    }

    existing_hooks = existing.get("hooks", {})

    # Merge without overwriting
    for event, configs in our_hooks.items():
        if event not in existing_hooks:
            existing_hooks[event] = configs
        else:
            # Check if our hook is already there
            existing_commands = [
                h.get("command", "")
                for cfg in existing_hooks[event]
                for h in cfg.get("hooks", [])
            ]
            for config in configs:
                for hook in config.get("hooks", []):
                    if hook.get("command") not in existing_commands:
                        existing_hooks[event].append(config)
                        break

    existing["hooks"] = existing_hooks
    return existing

def main():
    print("🔧 Setting up feedback collection hooks...\n")

    # Find settings file
    settings_path = find_settings_file()
    print(f"📁 Settings: {settings_path}")

    # Load existing settings
    existing = {}
    if settings_path.exists():
        existing = json.loads(settings_path.read_text())
        print("   Found existing settings")

    # Install hook scripts
    hooks_dir = get_hooks_dir()
    print(f"📁 Hooks: {hooks_dir}")
    install_hook_scripts(hooks_dir)
    print("   ✓ Hook scripts installed")

    # Merge configuration
    updated = merge_hooks_config(existing)

    # Save settings
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(updated, indent=2))
    print("   ✓ Settings updated")

    # Create feedback directory
    feedback_dir = Path.home() / ".feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Feedback DB: {feedback_dir}/feedback.db")

    print("\n✅ Setup complete!")
    print("\nNext steps:")
    print("  1. Run /hooks in Claude Code to review and approve hooks")
    print("  2. Use Claude Code normally - feedback is collected automatically")
    print("  3. Run `skill-insights` to view performance data")

if __name__ == "__main__":
    main()
```

### 3. Simplified Feedback Store (`feedback_store.py`)

```python
"""
SQLite feedback store - simplified for zero-config operation.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import json

@dataclass
class ToolExecution:
    session_id: str
    tool_name: str
    tool_input: Dict[str, Any]
    tool_response: Optional[Dict[str, Any]]
    success: bool
    error_message: Optional[str]
    duration_ms: Optional[int]
    skill_used: Optional[str]
    timestamp: str

@dataclass
class SessionSummary:
    session_id: str
    prompt: str
    tools_used: List[str]
    skills_detected: List[str]
    total_tool_calls: int
    successful_calls: int
    failed_calls: int
    task_completed: bool
    completion_feedback: Optional[str]
    timestamp: str

class FeedbackStore:
    """
    Zero-config feedback storage.

    Default location: ~/.feedback/feedback.db
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or (Path.home() / ".feedback" / "feedback.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize schema."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS tool_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                tool_input TEXT,
                tool_response TEXT,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                duration_ms INTEGER,
                skill_used TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS session_summaries (
                session_id TEXT PRIMARY KEY,
                prompt TEXT,
                tools_used TEXT,
                skills_detected TEXT,
                total_tool_calls INTEGER,
                successful_calls INTEGER,
                failed_calls INTEGER,
                task_completed BOOLEAN,
                completion_feedback TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_skill ON tool_executions(skill_used)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_session ON tool_executions(session_id)")

        conn.commit()
        conn.close()

    def log_tool_execution(self, execution: ToolExecution):
        """Log a tool execution."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            INSERT INTO tool_executions
            (session_id, tool_name, tool_input, tool_response, success,
             error_message, duration_ms, skill_used, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            execution.session_id,
            execution.tool_name,
            json.dumps(execution.tool_input),
            json.dumps(execution.tool_response) if execution.tool_response else None,
            execution.success,
            execution.error_message,
            execution.duration_ms,
            execution.skill_used,
            execution.timestamp
        ))

        conn.commit()
        conn.close()

    def log_session_summary(self, summary: SessionSummary):
        """Log session summary."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            INSERT OR REPLACE INTO session_summaries
            (session_id, prompt, tools_used, skills_detected, total_tool_calls,
             successful_calls, failed_calls, task_completed, completion_feedback, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            summary.session_id,
            summary.prompt,
            json.dumps(summary.tools_used),
            json.dumps(summary.skills_detected),
            summary.total_tool_calls,
            summary.successful_calls,
            summary.failed_calls,
            summary.task_completed,
            summary.completion_feedback,
            summary.timestamp
        ))

        conn.commit()
        conn.close()

    def get_session_executions(self, session_id: str) -> List[ToolExecution]:
        """Get all executions for a session."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            SELECT session_id, tool_name, tool_input, tool_response, success,
                   error_message, duration_ms, skill_used, timestamp
            FROM tool_executions WHERE session_id = ?
            ORDER BY timestamp
        """, (session_id,))

        results = [
            ToolExecution(
                session_id=r[0], tool_name=r[1],
                tool_input=json.loads(r[2]) if r[2] else {},
                tool_response=json.loads(r[3]) if r[3] else None,
                success=bool(r[4]), error_message=r[5],
                duration_ms=r[6], skill_used=r[7], timestamp=r[8]
            )
            for r in c.fetchall()
        ]

        conn.close()
        return results

    def get_skill_stats(self, skill_id: str = None) -> Dict[str, Any]:
        """Get performance stats, optionally filtered by skill."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        if skill_id:
            c.execute("""
                SELECT skill_used, COUNT(*) as total,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful
                FROM tool_executions
                WHERE skill_used = ?
                GROUP BY skill_used
            """, (skill_id,))
        else:
            c.execute("""
                SELECT skill_used, COUNT(*) as total,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful
                FROM tool_executions
                WHERE skill_used IS NOT NULL
                GROUP BY skill_used
            """)

        results = {}
        for row in c.fetchall():
            results[row[0]] = {
                "total": row[1],
                "successful": row[2],
                "failed": row[1] - row[2],
                "success_rate": row[2] / row[1] if row[1] > 0 else 0
            }

        conn.close()
        return results

    def get_common_errors(self, skill_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get common errors for a skill."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            SELECT error_message, COUNT(*) as count
            FROM tool_executions
            WHERE skill_used = ? AND NOT success AND error_message IS NOT NULL
            GROUP BY error_message
            ORDER BY count DESC
            LIMIT ?
        """, (skill_id, limit))

        results = [{"error": r[0], "count": r[1]} for r in c.fetchall()]
        conn.close()
        return results
```

### 4. Insights CLI (`cli.py`)

```python
#!/usr/bin/env python3
"""
Skill insights CLI.

Commands:
    skill-insights              Show all skill performance
    skill-insights SKILL        Show specific skill details
    skill-insights --errors     Show common errors
"""

import argparse
import json
from pathlib import Path

from feedback_store import FeedbackStore

def main():
    parser = argparse.ArgumentParser(description="View skill performance insights")
    parser.add_argument("skill", nargs="?", help="Specific skill to analyze")
    parser.add_argument("--errors", action="store_true", help="Show common errors")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    store = FeedbackStore()

    if args.skill:
        # Specific skill
        stats = store.get_skill_stats(args.skill)
        if args.skill not in stats:
            print(f"No data for skill: {args.skill}")
            return

        s = stats[args.skill]
        print(f"\n📊 {args.skill}")
        print(f"   Total uses: {s['total']}")
        print(f"   Success rate: {s['success_rate']:.1%}")
        print(f"   Failed: {s['failed']}")

        if args.errors:
            errors = store.get_common_errors(args.skill)
            if errors:
                print(f"\n   Common errors:")
                for e in errors[:5]:
                    print(f"   • ({e['count']}x) {e['error'][:60]}...")
    else:
        # All skills
        stats = store.get_skill_stats()

        if args.json:
            print(json.dumps(stats, indent=2))
            return

        if not stats:
            print("No skill usage data yet. Use Claude Code with skills, then check back!")
            return

        print("\n📊 Skill Performance Summary\n")
        print(f"{'Skill':<20} {'Uses':>8} {'Success':>10} {'Failed':>8}")
        print("-" * 50)

        for skill, s in sorted(stats.items(), key=lambda x: x[1]['total'], reverse=True):
            print(f"{skill:<20} {s['total']:>8} {s['success_rate']:>9.1%} {s['failed']:>8}")

        print()

if __name__ == "__main__":
    main()
```

---

## Installation

```bash
# Clone and install
git clone <repo>
cd pattern3-feedback-refinement
pip install -e .

# Auto-setup hooks
feedback-setup

# Review in Claude Code
# (Run /hooks to approve new hooks)

# View insights after some usage
skill-insights
```

---

## How Skill Detection Works (No Config Required)

The system uses a **cascade of strategies**, from most accurate to most general:

```
┌─────────────────────────────────────────────────────────────────┐
│                  SKILL DETECTION CASCADE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. TRANSCRIPT CONTEXT (Most Accurate)                          │
│     └─ Did Claude read a SKILL.md file in this session?        │
│        If yes → That's the skill being used                    │
│                                                                 │
│  2. LEARNED ASSOCIATIONS (Fast)                                 │
│     └─ Have we seen this tool+context pattern before?          │
│        If yes → Use the previously attributed skill            │
│                                                                 │
│  3. COLBERT INDEX QUERY (Semantic)                              │
│     └─ Query: "writing .docx files with python-docx"           │
│        Returns: docx skill (if score > 0.5)                    │
│        ⚠️ Requires Pattern 1 to be installed                   │
│                                                                 │
│  4. LLM INFERENCE (Comprehensive)                               │
│     └─ Ask LLM: "What skill handles this tool usage?"          │
│        Works for ANY skill, even custom ones                   │
│        ⚠️ Slower, requires LLM CLI                             │
│                                                                 │
│  5. UNKNOWN                                                     │
│     └─ If all strategies fail, skill_used = NULL               │
│        Still logs the execution for manual review              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

The system **learns over time**—once a pattern is attributed (by LLM or ColBERT), it's cached for instant future lookups.

---

## File Structure

```
pattern3-feedback-refinement/
├── CLAUDE.md
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── skill_detector.py      # Semantic skill detection
│   ├── feedback_store.py      # SQLite storage
│   ├── setup.py               # Auto-setup script
│   └── cli.py                 # Insights CLI
└── ~/.feedback/               # Data storage (auto-created)
    └── feedback.db
```

---

## Dependencies

```toml
[project]
name = "claude-skill-feedback"
version = "0.2.0"
requires-python = ">=3.10"
dependencies = []  # Pure Python!

[project.scripts]
feedback-setup = "src.setup:main"
skill-insights = "src.cli:main"

[project.optional-dependencies]
colbert = ["claude-skill-retrieval"]  # Pattern 1 for better detection
```

---

## Integration with Pattern 1

When both patterns are installed, they reinforce each other:

```
Pattern 1 (ColBERT Index)     Pattern 3 (Feedback)
         │                            │
         │  "find-skill" CLI          │
         └──────────────┬─────────────┘
                        │
              Skill Detection uses
              ColBERT for semantic
              matching (Strategy 3)
                        │
                        ▼
              Better attribution
              → Better insights
              → Better skill improvements
              → Better index
                        │
                        └──────────────┘
                         (Virtuous cycle)
```

Install both for best results:

```bash
pip install -e ../pattern1-colbert-skill-retrieval
pip install -e .
```

---

## Success Criteria

1. ✅ Zero configuration required
2. ✅ Works with ANY skill library
3. ✅ Auto-installs hooks
4. ✅ Semantic skill detection (no hardcoded mappings)
5. ✅ Learns from usage patterns
6. ✅ Integrates with Pattern 1 when available
7. ✅ Graceful degradation (works without LLM/ColBERT, just with less attribution)
