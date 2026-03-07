"""SQLite data access layer for opencode."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import FileChange, Message, Session


def _dt(value: Any) -> str:
    """Convert datetime to ISO string for SQLite storage."""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model TEXT,
    working_dir TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT,
    tool_calls TEXT,
    tool_results TEXT,
    model TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_changes (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    message_id TEXT REFERENCES messages(id),
    path TEXT NOT NULL,
    diff TEXT,
    action TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Store:
    """SQLite data store for sessions, messages, and file changes."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # --- Sessions ---

    def create_session(self, session: Session) -> Session:
        self._conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at, model, working_dir) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session.id, session.title, _dt(session.created_at), _dt(session.updated_at),
             session.model, session.working_dir),
        )
        self._conn.commit()
        return session

    def get_session(self, session_id: str) -> Session | None:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def list_sessions(self) -> list[Session]:
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def update_session(self, session_id: str, **fields: Any) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [session_id]
        self._conn.execute(
            f"UPDATE sessions SET {set_clause} WHERE id = ?", values  # noqa: S608
        )
        self._conn.commit()

    def delete_session(self, session_id: str) -> None:
        self._conn.execute("DELETE FROM file_changes WHERE session_id = ?", (session_id,))
        self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn.commit()

    # --- Messages ---

    def create_message(self, message: Message) -> Message:
        self._conn.execute(
            "INSERT INTO messages (id, session_id, role, content, tool_calls, "
            "tool_results, model, tokens_in, tokens_out, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (message.id, message.session_id, message.role, message.content,
             message.tool_calls, message.tool_results, message.model,
             message.tokens_in, message.tokens_out, _dt(message.created_at)),
        )
        self._conn.commit()
        return message

    def get_messages(self, session_id: str) -> list[Message]:
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def delete_message(self, message_id: str) -> None:
        self._conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        self._conn.commit()

    # --- File Changes ---

    def create_file_change(self, change: FileChange) -> FileChange:
        self._conn.execute(
            "INSERT INTO file_changes (id, session_id, message_id, path, diff, action, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (change.id, change.session_id, change.message_id, change.path,
             change.diff, change.action, _dt(change.created_at)),
        )
        self._conn.commit()
        return change

    def get_file_changes(self, session_id: str) -> list[FileChange]:
        rows = self._conn.execute(
            "SELECT * FROM file_changes WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [self._row_to_file_change(r) for r in rows]

    # --- Row mappers ---

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            title=row["title"] or "",
            model=row["model"] or "",
            working_dir=row["working_dir"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> Message:
        return Message(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"] or "",
            tool_calls=row["tool_calls"],
            tool_results=row["tool_results"],
            model=row["model"],
            tokens_in=row["tokens_in"],
            tokens_out=row["tokens_out"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_file_change(row: sqlite3.Row) -> FileChange:
        return FileChange(
            id=row["id"],
            session_id=row["session_id"],
            message_id=row["message_id"],
            path=row["path"],
            diff=row["diff"],
            action=row["action"] or "modify",
            created_at=row["created_at"],
        )
