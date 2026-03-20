"""Build-time context system — createContext/useContext (SolidJS parity).

Provider pushes a value during synchronous child construction, pops after.
use_context() reads the top of the stack.

Supports reactive context values: if the Provider value is a Signal,
ComputedSignal, or callable, use_context() returns the reactive source
directly so consumers can subscribe to changes.

Usage:
    ThemeContext = create_context("light")

    # Static value:
    ThemeContext.Provider(value="dark", children=[
        Text(content=lambda: use_context(ThemeContext)),
    ])

    # Reactive value:
    theme = Signal("dark")
    ThemeContext.Provider(value=theme, children=[
        Text(content=lambda: use_context(ThemeContext)()),  # call Signal
    ])
"""

from __future__ import annotations

import itertools
from typing import Any

from .components.base import BaseRenderable, Renderable

_ctx_counter = itertools.count()

_context_stacks: dict[int, list[Any]] = {}


class Context:
    """A typed context with a default value."""

    __slots__ = ("_id", "_default", "_name")

    def __init__(self, default: Any = None, name: str = "") -> None:
        self._id = next(_ctx_counter)
        self._default = default
        self._name = name

    def Provider(
        self, *, value: Any, children: list | None = None, **kwargs: Any
    ) -> BaseRenderable:
        """Create a context provider that wraps children.

        If ``value`` is a Signal, ComputedSignal, or callable, it is
        stored as-is so consumers can read it reactively.
        """
        return _make_context_provider(context=self, value=value, children=children, **kwargs)


def _make_context_provider(
    *, context: Context, value: Any, children: list | None = None, **kwargs: Any
) -> BaseRenderable:
    """Push context during child construction, pop after."""
    stack = _context_stacks.setdefault(context._id, [])
    stack.append(value)
    try:
        container = Renderable(**kwargs)
        if children:
            for child in children:
                if child is not None:
                    container.add(child)
    finally:
        stack.pop()
        if not stack:
            del _context_stacks[context._id]
    return container


def create_context(default: Any = None, name: str = "") -> Context:
    """Create a new context with an optional default value."""
    return Context(default, name)


def use_context(ctx: Context) -> Any:
    """Read the current value from a context.

    Returns the value from the nearest ancestor Provider, or the
    context's default if no Provider is in scope.

    If the Provider value is a Signal, ComputedSignal, or callable,
    the reactive source is returned directly (not unwrapped), matching
    SolidJS behavior where reactive context values must be explicitly
    read by the consumer.
    """
    stack = _context_stacks.get(ctx._id)
    return stack[-1] if stack else ctx._default


__all__ = [
    "Context",
    "create_context",
    "use_context",
]
