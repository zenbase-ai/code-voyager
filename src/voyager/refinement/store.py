"""SQLite-backed feedback store for skill refinement.

Stores tool execution logs, skill attributions, and learned associations
with zero-config defaults. Default location: ./.claude/voyager/feedback.db
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voyager.config import get_feedback_db_path
from voyager.logging import get_logger

_logger = get_logger("refinement.store")


@dataclass
class ToolExecution:
    """Record of a single tool execution."""

    session_id: str
    tool_name: str
    tool_input: dict[str, Any]
    tool_response: dict[str, Any] | None
    success: bool
    error_message: str | None
    duration_ms: int | None
    skill_used: str | None
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_response": self.tool_response,
            "success": self.success,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "skill_used": self.skill_used,
            "timestamp": self.timestamp,
        }


@dataclass
class SessionSummary:
    """Summary of a Claude Code session."""

    session_id: str
    prompt: str
    tools_used: list[str]
    skills_detected: list[str]
    total_tool_calls: int
    successful_calls: int
    failed_calls: int
    task_completed: bool
    completion_feedback: str | None
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "session_id": self.session_id,
            "prompt": self.prompt,
            "tools_used": self.tools_used,
            "skills_detected": self.skills_detected,
            "total_tool_calls": self.total_tool_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "task_completed": self.task_completed,
            "completion_feedback": self.completion_feedback,
            "timestamp": self.timestamp,
        }


class FeedbackStore:
    """SQLite-backed feedback storage.

    Default location: .claude/voyager/feedback.db (project-local)
    Falls back to ~/.claude/voyager/feedback.db if no project dir available.
    """

    def __init__(self, db_path: Path | str | None = None):
        """Initialize the store.

        Args:
            db_path: Path to SQLite database. Defaults to project-local path.
        """
        if db_path is None:
            db_path = get_feedback_db_path()
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        c = conn.cursor()

        # Tool executions table
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

        # Session summaries table
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

        # Learned associations table (for fast skill detection)
        c.execute("""
            CREATE TABLE IF NOT EXISTS learned_associations (
                context_key TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                hit_count INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Indexes for common queries
        c.execute("CREATE INDEX IF NOT EXISTS idx_tool_executions_skill ON tool_executions(skill_used)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tool_executions_session ON tool_executions(session_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tool_executions_tool ON tool_executions(tool_name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tool_executions_success ON tool_executions(success)")

        conn.commit()
        conn.close()
        _logger.debug("Initialized feedback database at %s", self.db_path)

    def log_tool_execution(self, execution: ToolExecution) -> int:
        """Log a tool execution.

        Args:
            execution: The tool execution record.

        Returns:
            The row ID of the inserted record.
        """
        conn = self._get_connection()
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO tool_executions
            (session_id, tool_name, tool_input, tool_response, success,
             error_message, duration_ms, skill_used, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution.session_id,
                execution.tool_name,
                json.dumps(execution.tool_input),
                json.dumps(execution.tool_response) if execution.tool_response else None,
                execution.success,
                execution.error_message,
                execution.duration_ms,
                execution.skill_used,
                execution.timestamp,
            ),
        )

        row_id = c.lastrowid
        conn.commit()
        conn.close()
        _logger.debug(
            "Logged tool execution: %s (skill=%s, success=%s)",
            execution.tool_name,
            execution.skill_used,
            execution.success,
        )
        return row_id or 0

    def log_session_summary(self, summary: SessionSummary) -> None:
        """Log or update a session summary.

        Args:
            summary: The session summary record.
        """
        conn = self._get_connection()
        c = conn.cursor()

        c.execute(
            """
            INSERT OR REPLACE INTO session_summaries
            (session_id, prompt, tools_used, skills_detected, total_tool_calls,
             successful_calls, failed_calls, task_completed, completion_feedback, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary.session_id,
                summary.prompt,
                json.dumps(summary.tools_used),
                json.dumps(summary.skills_detected),
                summary.total_tool_calls,
                summary.successful_calls,
                summary.failed_calls,
                summary.task_completed,
                summary.completion_feedback,
                summary.timestamp,
            ),
        )

        conn.commit()
        conn.close()
        _logger.debug("Logged session summary for %s", summary.session_id)

    def get_session_executions(self, session_id: str) -> list[ToolExecution]:
        """Get all executions for a session.

        Args:
            session_id: Session identifier.

        Returns:
            List of tool execution records.
        """
        conn = self._get_connection()
        c = conn.cursor()

        c.execute(
            """
            SELECT session_id, tool_name, tool_input, tool_response, success,
                   error_message, duration_ms, skill_used, timestamp
            FROM tool_executions WHERE session_id = ?
            ORDER BY timestamp
            """,
            (session_id,),
        )

        results = [
            ToolExecution(
                session_id=r["session_id"],
                tool_name=r["tool_name"],
                tool_input=json.loads(r["tool_input"]) if r["tool_input"] else {},
                tool_response=json.loads(r["tool_response"]) if r["tool_response"] else None,
                success=bool(r["success"]),
                error_message=r["error_message"],
                duration_ms=r["duration_ms"],
                skill_used=r["skill_used"],
                timestamp=r["timestamp"],
            )
            for r in c.fetchall()
        ]

        conn.close()
        return results

    def get_skill_stats(self, skill_id: str | None = None) -> dict[str, Any]:
        """Get performance stats, optionally filtered by skill.

        Args:
            skill_id: Optional skill ID to filter by.

        Returns:
            Dict mapping skill_id to stats (total, successful, failed, success_rate).
        """
        conn = self._get_connection()
        c = conn.cursor()

        if skill_id:
            c.execute(
                """
                SELECT skill_used, COUNT(*) as total,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful
                FROM tool_executions
                WHERE skill_used = ?
                GROUP BY skill_used
                """,
                (skill_id,),
            )
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
            total = row["total"]
            successful = row["successful"]
            results[row["skill_used"]] = {
                "total": total,
                "successful": successful,
                "failed": total - successful,
                "success_rate": successful / total if total > 0 else 0,
            }

        conn.close()
        return results

    def get_common_errors(self, skill_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        """Get common errors, optionally filtered by skill.

        Args:
            skill_id: Optional skill ID to filter by.
            limit: Maximum number of errors to return.

        Returns:
            List of dicts with error and count.
        """
        conn = self._get_connection()
        c = conn.cursor()

        if skill_id:
            c.execute(
                """
                SELECT error_message, COUNT(*) as count, tool_name
                FROM tool_executions
                WHERE skill_used = ? AND NOT success AND error_message IS NOT NULL
                GROUP BY error_message
                ORDER BY count DESC
                LIMIT ?
                """,
                (skill_id, limit),
            )
        else:
            c.execute(
                """
                SELECT error_message, COUNT(*) as count, tool_name, skill_used
                FROM tool_executions
                WHERE NOT success AND error_message IS NOT NULL
                GROUP BY error_message
                ORDER BY count DESC
                LIMIT ?
                """,
                (limit,),
            )

        results = [
            {
                "error": r["error_message"],
                "count": r["count"],
                "tool": r["tool_name"],
                "skill": skill_id if skill_id else r.get("skill_used"),
            }
            for r in c.fetchall()
        ]

        conn.close()
        return results

    def get_tool_usage_stats(self) -> dict[str, dict[str, Any]]:
        """Get tool usage statistics.

        Returns:
            Dict mapping tool_name to stats (total, successful, failed, success_rate).
        """
        conn = self._get_connection()
        c = conn.cursor()

        c.execute("""
            SELECT tool_name, COUNT(*) as total,
                   SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful
            FROM tool_executions
            GROUP BY tool_name
            ORDER BY total DESC
        """)

        results = {}
        for row in c.fetchall():
            total = row["total"]
            successful = row["successful"]
            results[row["tool_name"]] = {
                "total": total,
                "successful": successful,
                "failed": total - successful,
                "success_rate": successful / total if total > 0 else 0,
            }

        conn.close()
        return results

    # Learned associations methods

    def get_learned_association(self, context_key: str) -> str | None:
        """Get a learned skill association.

        Args:
            context_key: The context key to look up.

        Returns:
            The skill_id if found, None otherwise.
        """
        conn = self._get_connection()
        c = conn.cursor()

        c.execute(
            "SELECT skill_id FROM learned_associations WHERE context_key = ?",
            (context_key,),
        )
        row = c.fetchone()
        conn.close()

        return row["skill_id"] if row else None

    def learn_association(self, context_key: str, skill_id: str, confidence: float = 1.0) -> None:
        """Learn or reinforce a tool context → skill association.

        Args:
            context_key: The context key (tool+extension+command).
            skill_id: The skill ID to associate.
            confidence: Confidence score (0-1).
        """
        conn = self._get_connection()
        c = conn.cursor()

        now = datetime.now(UTC).isoformat()

        # Try to update existing, or insert new
        c.execute(
            """
            INSERT INTO learned_associations
            (context_key, skill_id, confidence, hit_count, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(context_key) DO UPDATE SET
                skill_id = excluded.skill_id,
                confidence = (confidence * hit_count + excluded.confidence) / (hit_count + 1),
                hit_count = hit_count + 1,
                updated_at = excluded.updated_at
            """,
            (context_key, skill_id, confidence, now, now),
        )

        conn.commit()
        conn.close()
        _logger.debug("Learned association: %s -> %s", context_key, skill_id)

    def get_all_learned_associations(self) -> dict[str, str]:
        """Get all learned associations as a dict.

        Returns:
            Dict mapping context_key to skill_id.
        """
        conn = self._get_connection()
        c = conn.cursor()

        c.execute("SELECT context_key, skill_id FROM learned_associations")
        results = {r["context_key"]: r["skill_id"] for r in c.fetchall()}

        conn.close()
        return results

    def get_recent_sessions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent session summaries.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of session summary dicts.
        """
        conn = self._get_connection()
        c = conn.cursor()

        c.execute(
            """
            SELECT * FROM session_summaries
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

        results = []
        for row in c.fetchall():
            results.append(
                {
                    "session_id": row["session_id"],
                    "prompt": row["prompt"],
                    "tools_used": json.loads(row["tools_used"]) if row["tools_used"] else [],
                    "skills_detected": json.loads(row["skills_detected"]) if row["skills_detected"] else [],
                    "total_tool_calls": row["total_tool_calls"],
                    "successful_calls": row["successful_calls"],
                    "failed_calls": row["failed_calls"],
                    "task_completed": row["task_completed"],
                    "completion_feedback": row["completion_feedback"],
                    "timestamp": row["timestamp"],
                }
            )

        conn.close()
        return results

    def get_total_counts(self) -> dict[str, int]:
        """Get total counts for quick stats.

        Returns:
            Dict with total_executions, total_sessions, total_skills.
        """
        conn = self._get_connection()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) as count FROM tool_executions")
        total_executions = c.fetchone()["count"]

        c.execute("SELECT COUNT(DISTINCT session_id) as count FROM tool_executions")
        total_sessions = c.fetchone()["count"]

        c.execute("SELECT COUNT(DISTINCT skill_used) as count FROM tool_executions WHERE skill_used IS NOT NULL")
        total_skills = c.fetchone()["count"]

        conn.close()
        return {
            "total_executions": total_executions,
            "total_sessions": total_sessions,
            "total_skills": total_skills,
        }

    def reset(self) -> None:
        """Reset the database (delete all data)."""
        conn = self._get_connection()
        c = conn.cursor()

        c.execute("DELETE FROM tool_executions")
        c.execute("DELETE FROM session_summaries")
        c.execute("DELETE FROM learned_associations")

        conn.commit()
        conn.close()
        _logger.info("Reset feedback database")
