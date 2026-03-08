"""SQLite data access layer for opencode."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .models import FileChange, Message, MessagePart, Session


def _dt(value: Any) -> str:
    """Convert datetime to ISO string for SQLite storage."""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _parse_dt(value: Any) -> datetime:
    """Parse an ISO string back to datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Expected datetime or ISO-format string, got {type(value).__name__}")


_SESSION_COLUMNS = frozenset({"title", "model", "working_dir", "updated_at"})

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
    session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT,
    tool_calls TEXT,
    tool_results TEXT,
    model TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message_parts (
    id TEXT PRIMARY KEY,
    message_id TEXT REFERENCES messages(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    content TEXT,
    tool_name TEXT,
    tool_call_id TEXT,
    metadata TEXT,
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_changes (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    message_id TEXT REFERENCES messages(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    diff TEXT,
    action TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Store:
    """SQLite data store for sessions, messages, and file changes."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._in_batch = False
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _commit(self) -> None:
        """Commit unless inside a batch() context."""
        if not self._in_batch:
            self._conn.commit()

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Context manager that defers commits until the block completes."""
        self._in_batch = True
        try:
            yield
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        finally:
            self._in_batch = False

    # --- Sessions ---

    def create_session(self, session: Session) -> Session:
        self._conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at, model, working_dir) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session.id, session.title, _dt(session.created_at), _dt(session.updated_at),
             session.model, session.working_dir),
        )
        self._commit()
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
        bad = set(fields) - _SESSION_COLUMNS
        if bad:
            raise ValueError(f"Invalid column(s): {bad}")
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = [_dt(v) if isinstance(v, datetime) else v for v in fields.values()]
        values.append(session_id)
        self._conn.execute(
            f"UPDATE sessions SET {set_clause} WHERE id = ?", values  # noqa: S608
        )
        self._commit()

    def delete_session(self, session_id: str) -> None:
        self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._commit()

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
        self._commit()
        return message

    def get_messages(self, session_id: str) -> list[Message]:
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def delete_message(self, message_id: str) -> None:
        # file_changes are removed automatically via ON DELETE CASCADE
        self._conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        self._commit()

    # --- Message Parts ---

    def create_message_part(self, part: MessagePart) -> MessagePart:
        self._conn.execute(
            "INSERT INTO message_parts (id, message_id, type, content, tool_name, "
            "tool_call_id, metadata, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (part.id, part.message_id, part.type, part.content, part.tool_name,
             part.tool_call_id, part.metadata, part.status, _dt(part.created_at)),
        )
        self._commit()
        return part

    def get_message_parts(self, message_id: str) -> list[MessagePart]:
        rows = self._conn.execute(
            "SELECT * FROM message_parts WHERE message_id = ? ORDER BY created_at",
            (message_id,),
        ).fetchall()
        return [self._row_to_message_part(r) for r in rows]

    def get_session_parts(self, session_id: str) -> dict[str, list[MessagePart]]:
        """Get all parts for all messages in a session, keyed by message_id."""
        rows = self._conn.execute(
            "SELECT mp.* FROM message_parts mp "
            "JOIN messages m ON mp.message_id = m.id "
            "WHERE m.session_id = ? ORDER BY mp.created_at",
            (session_id,),
        ).fetchall()
        parts: dict[str, list[MessagePart]] = {}
        for r in rows:
            p = self._row_to_message_part(r)
            parts.setdefault(p.message_id, []).append(p)
        return parts

    def update_message_part(self, part_id: str, **fields: Any) -> None:
        allowed = {"content", "status", "metadata"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"Invalid column(s): {bad}")
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values())
        values.append(part_id)
        self._conn.execute(
            f"UPDATE message_parts SET {set_clause} WHERE id = ?", values  # noqa: S608
        )
        self._commit()

    # --- File Changes ---

    def create_file_change(self, change: FileChange) -> FileChange:
        self._conn.execute(
            "INSERT INTO file_changes (id, session_id, message_id, path, diff, action, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (change.id, change.session_id, change.message_id, change.path,
             change.diff, change.action, _dt(change.created_at)),
        )
        self._commit()
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
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
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
            created_at=_parse_dt(row["created_at"]),
        )

    @staticmethod
    def _row_to_message_part(row: sqlite3.Row) -> MessagePart:
        return MessagePart(
            id=row["id"],
            message_id=row["message_id"],
            type=row["type"],
            content=row["content"] or "",
            tool_name=row["tool_name"],
            tool_call_id=row["tool_call_id"],
            metadata=row["metadata"],
            status=row["status"] or "completed",
            created_at=_parse_dt(row["created_at"]),
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
            created_at=_parse_dt(row["created_at"]),
        )
