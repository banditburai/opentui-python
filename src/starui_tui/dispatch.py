"""Event dispatch for declarative actions."""

from __future__ import annotations

from typing import Any

from .actions import Action


def dispatch_action(action_or_fn: Action | list | Any | None) -> None:
    """Execute an action, list of actions, or callable.

    Handles:
    - Single Action instance → execute()
    - List of actions/callables → dispatch each recursively
    - Callable → call it
    - None → no-op
    """
    if action_or_fn is None:
        return
    if isinstance(action_or_fn, Action):
        action_or_fn.execute()
    elif isinstance(action_or_fn, list):
        for item in action_or_fn:
            dispatch_action(item)
    elif callable(action_or_fn):
        action_or_fn()
