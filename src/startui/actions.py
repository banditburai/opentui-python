"""Declarative Action classes for event handling.

Actions describe what should happen on an event. They can be returned
by signal methods during declaration context, enabling syntax like:
    Button("Increment", on_click=counter.add(1))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .signals import Signal


class Action:
    """Base class for declarative event actions."""

    __slots__ = ()

    def execute(self) -> None:
        """Execute this action."""
        raise NotImplementedError("Subclasses must implement execute()")


class SetAction(Action):
    """Set a signal to a specific value."""

    __slots__ = ("signal", "value")

    def __init__(self, signal: Signal, value: Any) -> None:
        self.signal = signal
        self.value = value

    def execute(self) -> None:
        self.signal.set(self.value)


class AddAction(Action):
    """Add a delta to a signal's current value."""

    __slots__ = ("signal", "delta")

    def __init__(self, signal: Signal, delta: Any) -> None:
        self.signal = signal
        self.delta = delta

    def execute(self) -> None:
        self.signal.add(self.delta)


class ToggleAction(Action):
    """Toggle a signal's boolean value."""

    __slots__ = ("signal",)

    def __init__(self, signal: Signal) -> None:
        self.signal = signal

    def execute(self) -> None:
        self.signal.toggle()


class CallAction(Action):
    """Call a function with optional arguments."""

    __slots__ = ("fn", "args", "kwargs")

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def execute(self) -> None:
        self.fn(*self.args, **self.kwargs)


class SequenceAction(Action):
    """Execute multiple actions in sequence."""

    __slots__ = ("actions",)

    def __init__(self, *actions: Action) -> None:
        self.actions = actions

    def execute(self) -> None:
        for action in self.actions:
            action.execute()
