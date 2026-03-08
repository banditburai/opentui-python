"""Signal bridge — maps Python state to Datastar signals."""

from __future__ import annotations

from starhtml import Signal


def app_signals() -> dict[str, Signal]:
    """Create the set of Datastar signals for the web UI."""
    return {
        "prompt": Signal("prompt", ""),
        "status": Signal("status", "Ready"),
        "model": Signal("model", ""),
        "session_id": Signal("session_id", ""),
        "streaming": Signal("streaming", False),
        "sidebar_open": Signal("sidebar_open", True),
        "theme": Signal("theme", "opencode"),
        "theme_mode": Signal("theme_mode", "dark"),
        "command_palette_open": Signal("command_palette_open", False),
        "command_query": Signal("command_query", ""),
    }
