"""Overlay manager — LIFO stack of modal overlays rendered on top of main layout."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from opentui.components import Box, Text
from opentui.signals import Signal

from .themes import get_theme


class OverlayManager:
    """Manages a LIFO stack of overlay components.

    Each overlay is a callable returning a Box node.
    Escape pops the top overlay; overlays capture keyboard input.
    """

    def __init__(self) -> None:
        self._stack: Signal = Signal("overlay_stack", [])

    @property
    def count(self) -> int:
        return len(self._stack())

    @property
    def is_active(self) -> bool:
        return self.count > 0

    def push(self, overlay: Callable[[], Box]) -> None:
        """Push an overlay onto the stack."""
        stack = list(self._stack())
        stack.append(overlay)
        self._stack.set(stack)

    def pop(self) -> Callable[[], Box] | None:
        """Pop and return the top overlay, or None if empty."""
        stack = list(self._stack())
        if not stack:
            return None
        removed = stack.pop()
        self._stack.set(stack)
        return removed

    def peek(self) -> Callable[[], Box] | None:
        """Return the top overlay without removing it."""
        stack = self._stack()
        return stack[-1] if stack else None

    def clear(self) -> None:
        """Remove all overlays."""
        self._stack.set([])

    def render(self, base: Box) -> Box:
        """Render base layout with overlay stack on top.

        If no overlays are active, returns *base* unchanged.
        """
        stack = self._stack()
        if not stack:
            return base

        layers: list[Box] = [base]

        for overlay_fn in stack:
            layers.append(overlay_fn())

        return Box(*layers, flex_direction="column")


# Module-level singleton
_overlay_manager: OverlayManager | None = None


def get_overlay_manager() -> OverlayManager:
    """Return the global overlay manager (created on first call)."""
    global _overlay_manager
    if _overlay_manager is None:
        _overlay_manager = OverlayManager()
    return _overlay_manager


def reset_overlay_manager() -> None:
    """Reset the global overlay manager (useful for testing)."""
    global _overlay_manager
    _overlay_manager = None
