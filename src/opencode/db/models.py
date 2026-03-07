"""SQLite models for sessions, messages, and file changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Session:
    id: str
    title: str = ""
    model: str = ""
    working_dir: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


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
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class FileChange:
    id: str
    session_id: str
    message_id: str
    path: str
    diff: str | None = None
    action: str = "modify"  # 'create', 'modify', 'delete'
    created_at: datetime = field(default_factory=datetime.now)
