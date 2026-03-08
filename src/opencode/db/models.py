"""SQLite models for sessions, messages, and file changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Session:
    id: str
    title: str = ""
    model: str = ""
    working_dir: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Message:
    id: str
    session_id: str
    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str = ""
    tool_calls: str | None = None  # JSON
    tool_results: str | None = None  # JSON
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MessagePart:
    """A typed part within a message (text, tool_call, tool_result, reasoning, error)."""

    id: str
    message_id: str
    type: str  # 'text', 'tool_call', 'tool_result', 'reasoning', 'error'
    content: str = ""
    tool_name: str | None = None
    tool_call_id: str | None = None
    metadata: str | None = None  # JSON
    status: str = "completed"  # 'pending', 'running', 'completed', 'error'
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class FileChange:
    id: str
    session_id: str
    message_id: str
    path: str
    diff: str | None = None
    action: str = "modify"  # 'create', 'modify', 'delete'
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
