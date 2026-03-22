"""Input package — key parsing, key binding, stdin buffering, and event loop."""

from .event_loop import EventLoop, TestInputHandler
from .handler import InputHandler
from .key_handler import InternalKeyHandler, KeyHandler
from .key_maps import NON_ALPHANUMERIC_KEYS
from .keymapping import (
    DEFAULT_KEY_ALIASES,
    KeyBinding,
    build_key_bindings_map,
    init_key_bindings,
    key_binding_to_string,
    lookup_action,
    lookup_action_for_event,
    merge_key_aliases,
    merge_key_bindings,
)
from .stdin_buffer import StdinBuffer

__all__ = [
    "DEFAULT_KEY_ALIASES",
    "EventLoop",
    "InputHandler",
    "InternalKeyHandler",
    "KeyBinding",
    "KeyHandler",
    "NON_ALPHANUMERIC_KEYS",
    "StdinBuffer",
    "TestInputHandler",
    "build_key_bindings_map",
    "init_key_bindings",
    "key_binding_to_string",
    "lookup_action",
    "lookup_action_for_event",
    "merge_key_aliases",
    "merge_key_bindings",
]
