"""Layout diagnostics for OpenTUI.

Provides category-gated diagnostic logging for debugging silent rendering
failures: zero-size layouts, invisible nodes, stale dirty flags, etc.

Activate via environment variable::

    OPENTUI_DEBUG=layout,visibility,resize python my_app.py

Or programmatically::

    from opentui import enable_diagnostics, disable_diagnostics
    enable_diagnostics("layout", "visibility")

Categories are additive — calling ``enable_diagnostics`` multiple times ORs
with any previously enabled categories.  Use ``disable_diagnostics()`` to
clear all, or pass ``replace=True`` to start fresh.

Diagnostics are written to a log file (not stderr/stdout) since TUI apps
take over the terminal.  The default path is ``opentui-debug.log`` in the
current working directory.  Override with ``OPENTUI_DEBUG_LOG=<path>``.

The log file path is printed to stderr before the TUI starts so you know
where to ``tail -f``.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Category bitmask constants
# ---------------------------------------------------------------------------

RESIZE = 1 << 0  # Terminal resize events
LAYOUT = 1 << 1  # Yoga layout application + zero-size warnings
VISIBILITY = 1 << 2  # _visible transitions, Show/Switch/For branch changes
DIRTY = 1 << 3  # mark_dirty / mark_paint_dirty propagation
ALL = RESIZE | LAYOUT | VISIBILITY | DIRTY

_CATEGORY_MAP: dict[str, int] = {
    "resize": RESIZE,
    "layout": LAYOUT,
    "visibility": VISIBILITY,
    "dirty": DIRTY,
    "all": ALL,
}

# ---------------------------------------------------------------------------
# Module-level fast-check (hot path is `if _enabled:` → ~1ns when off)
# ---------------------------------------------------------------------------

_enabled: int = 0
_log = logging.getLogger("opentui.diagnostics")
_log_file_path: str | None = None

_DEFAULT_LOG_FILE = "opentui-debug.log"


def _ensure_handler() -> None:
    """Attach a file handler for diagnostic output.

    TUI apps take over the terminal, so we write to a file instead of
    stderr.  The path defaults to ``opentui-debug.log`` in cwd and can
    be overridden with ``OPENTUI_DEBUG_LOG``.

    Prints the log file path to stderr once so the developer knows where
    to ``tail -f``.
    """
    global _log_file_path
    if _log.handlers:
        return

    log_path = os.environ.get("OPENTUI_DEBUG_LOG", "").strip()
    if not log_path:
        log_path = str(Path.cwd() / _DEFAULT_LOG_FILE)

    _log_file_path = log_path

    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S.%f")
    )
    _log.addHandler(handler)
    _log.setLevel(logging.DEBUG)

    # Print path to stderr *before* the TUI takes over the screen
    print(f"[opentui] diagnostics → {log_path}", file=sys.stderr, flush=True)


def enable_diagnostics(*categories: str, replace: bool = False) -> None:
    """Enable diagnostic logging for the given categories.

    Categories are ORed with any already-enabled categories unless
    *replace* is ``True``.

    Valid categories: ``"resize"``, ``"layout"``, ``"visibility"``,
    ``"dirty"``, ``"all"``.
    """
    global _enabled
    mask = 0 if replace else _enabled
    for cat in categories:
        bits = _CATEGORY_MAP.get(cat.lower())
        if bits is None:
            raise ValueError(
                f"Unknown diagnostics category {cat!r}. Valid: {', '.join(sorted(_CATEGORY_MAP))}"
            )
        mask |= bits
    _enabled = mask
    if _enabled:
        _ensure_handler()


def disable_diagnostics() -> None:
    """Disable all diagnostic logging."""
    global _enabled
    _enabled = 0


def _init_from_env() -> None:
    """Read ``OPENTUI_DEBUG`` and enable matching categories.

    Called at module import time.  The env var is a comma-separated list of
    category names (e.g. ``"layout,visibility,resize"``).
    """
    raw = os.environ.get("OPENTUI_DEBUG", "")
    if not raw:
        return
    cats = [c.strip() for c in raw.split(",") if c.strip()]
    if cats:
        enable_diagnostics(*cats)


def get_log_file_path() -> str | None:
    """Return the active log file path, or ``None`` if diagnostics are off."""
    return _log_file_path


# ---------------------------------------------------------------------------
# Diagnostic log helpers (each guards on its own category bit)
# ---------------------------------------------------------------------------


def _node_label(node: Any, depth: int = 2) -> str:
    """Return a human-readable label like ``Box > Row#header > Text``."""
    parts: list[str] = []
    n = node
    for _ in range(depth + 1):
        if n is None:
            break
        cls = type(n).__name__
        nid = getattr(n, "_id", "") or ""
        parts.append(f"{cls}#{nid}" if nid else cls)
        n = getattr(n, "_parent", None)
    return " > ".join(reversed(parts))


def log_resize(old_w: int, old_h: int, new_w: int, new_h: int) -> None:
    _log.debug("resize: %dx%d -> %dx%d", old_w, old_h, new_w, new_h)


def log_layout_facts(facts: list[Any] | None) -> None:
    if not facts:
        return
    for fact in facts:
        node = fact[0]
        old_x, old_y, old_w, old_h = fact[4], fact[5], fact[6], fact[7]
        new_x, new_y, new_w, new_h = fact[8], fact[9], fact[10], fact[11]
        label = _node_label(node)
        if new_w == 0 and new_h == 0 and (old_w != 0 or old_h != 0):
            _log.warning(
                "layout: %s %dx%d@(%d,%d) -> 0x0@(%d,%d) (collapsed to zero)",
                label,
                old_w,
                old_h,
                old_x,
                old_y,
                new_x,
                new_y,
            )
        elif (new_x, new_y, new_w, new_h) != (old_x, old_y, old_w, old_h):
            _log.debug(
                "layout: %s %dx%d@(%d,%d) -> %dx%d@(%d,%d)",
                label,
                old_w,
                old_h,
                old_x,
                old_y,
                new_w,
                new_h,
                new_x,
                new_y,
            )
        # Check min constraint violations (only for numeric min values)
        min_w = getattr(node, "_min_width", None)
        min_h = getattr(node, "_min_height", None)
        if isinstance(min_w, (int, float)) and 0 < new_w < min_w:
            _log.warning(
                "layout: %s min_width=%s but got width=%d (constraint overridden by parent)",
                label,
                min_w,
                new_w,
            )
        if isinstance(min_h, (int, float)) and 0 < new_h < min_h:
            _log.warning(
                "layout: %s min_height=%s but got height=%d (constraint overridden by parent)",
                label,
                min_h,
                new_h,
            )


def log_visibility_change(node: Any, old_val: bool, new_val: bool) -> None:
    _log.debug("visibility: %s._visible %s -> %s", _node_label(node), old_val, new_val)


def log_show_branch(
    show_node: Any,
    condition: Any,
    old_branch: str,
    new_branch: str,
    cached: bool,
) -> None:
    _log.debug(
        'show: %s condition=%s branch="%s"->"%s"%s',
        _node_label(show_node),
        condition,
        old_branch,
        new_branch,
        " (cached)" if cached else "",
    )


def log_switch_branch(
    switch_node: Any,
    branch_key: Any,
    old_key: Any,
    cached: bool,
) -> None:
    _log.debug(
        "switch: %s branch=%s->%s%s",
        _node_label(switch_node),
        old_key,
        branch_key,
        " (cached)" if cached else "",
    )


def log_for_reconcile(
    for_node: Any,
    old_count: int,
    new_count: int,
) -> None:
    _log.debug(
        "for: %s items %d -> %d",
        _node_label(for_node),
        old_count,
        new_count,
    )


def log_dirty(node: Any, dirty_type: str) -> None:
    _log.debug("dirty: %s %s", _node_label(node), dirty_type)


# ---------------------------------------------------------------------------
# Auto-init from environment at import time
# ---------------------------------------------------------------------------

_init_from_env()
