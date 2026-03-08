"""History and stash persistence — JSONL files for prompt history and stash."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

MAX_ENTRIES = 50


def _data_dir() -> Path:
    """Return the OpenCode data directory, creating it if needed."""
    d = Path.home() / ".local" / "share" / "opencode"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def load_history(name: str = "prompt") -> list[str]:
    """Load history entries from a JSONL file."""
    path = _data_dir() / f"{name}_history.jsonl"
    if not path.is_file():
        return []
    entries: list[str] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        log.warning("Failed to read history file %s", path)
    return entries[-MAX_ENTRIES:]


def save_history(entries: list[str], name: str = "prompt") -> None:
    """Save history entries to a JSONL file (keeps last MAX_ENTRIES)."""
    path = _data_dir() / f"{name}_history.jsonl"
    trimmed = entries[-MAX_ENTRIES:]
    try:
        path.write_text("\n".join(json.dumps(e) for e in trimmed) + "\n")
    except OSError:
        log.warning("Failed to write history file %s", path)


def append_history(entry: str, name: str = "prompt") -> None:
    """Append a single entry to history."""
    entries = load_history(name)
    entries.append(entry)
    save_history(entries, name)


# ---------------------------------------------------------------------------
# Stash
# ---------------------------------------------------------------------------


def load_stash() -> list[dict]:
    """Load stash entries from JSONL."""
    path = _data_dir() / "stash.jsonl"
    if not path.is_file():
        return []
    entries: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        log.warning("Failed to read stash file")
    return entries[-MAX_ENTRIES:]


def save_stash(entries: list[dict]) -> None:
    """Save stash entries to JSONL."""
    path = _data_dir() / "stash.jsonl"
    trimmed = entries[-MAX_ENTRIES:]
    try:
        path.write_text("\n".join(json.dumps(e) for e in trimmed) + "\n")
    except OSError:
        log.warning("Failed to write stash file")


def push_stash(text: str, label: str = "") -> None:
    """Push text to stash with optional label."""
    import time

    entries = load_stash()
    entries.append({"text": text, "label": label, "timestamp": time.time()})
    save_stash(entries)


def pop_stash() -> dict | None:
    """Pop the most recent stash entry."""
    entries = load_stash()
    if not entries:
        return None
    entry = entries.pop()
    save_stash(entries)
    return entry
