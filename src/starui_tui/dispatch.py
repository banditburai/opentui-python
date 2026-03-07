"""Event dispatch for declarative actions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable

from .actions import Action


def dispatch_action(action_or_fn: Action | Sequence | Callable | None) -> None:
    """Execute an action, sequence of actions, or callable.

    Handles:
    - Single Action instance -> execute()
    - List/tuple of actions/callables -> dispatch each recursively
    - Callable -> call it
    - None -> no-op

    Raises TypeError for unrecognized types.
    """
    if action_or_fn is None:
        return
    if isinstance(action_or_fn, Action):
        action_or_fn.execute()
    elif isinstance(action_or_fn, (list, tuple)):
        for item in action_or_fn:
            dispatch_action(item)
    elif callable(action_or_fn):
        action_or_fn()
    else:
        raise TypeError(f"Cannot dispatch {type(action_or_fn).__name__}: expected Action, list, tuple, callable, or None")
