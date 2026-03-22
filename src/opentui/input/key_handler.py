"""KeyHandler and InternalKeyHandler for OpenTUI.

KeyHandler parses raw terminal input into KeyEvent/PasteEvent and dispatches
them to registered listeners.

InternalKeyHandler extends KeyHandler with a priority system:
global handlers run first, then internal (renderable) handlers —
unless preventDefault() was called.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from typing import Any

from ..events import KeyEvent, PasteEvent
from .key_maps import _ANSI_RE, _KITTY_KEY_MAP, _KITTY_KEY_RE, _SGR_MOUSE_RE

_log = logging.getLogger(__name__)

_SPECIAL_CTRL: dict[str, str] = {
    "\r": "return",
    "\n": "enter",
    "\t": "tab",
    "\b": "backspace",
    "\x7f": "backspace",
}


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def parse_keypress(data: str, *, use_kitty_keyboard: bool = False) -> KeyEvent | None:
    """Parse a raw input string into a KeyEvent, or None if not a key event.

    This is a stateless parser for single key sequences.
    """
    if not data:
        return None

    if _SGR_MOUSE_RE.match(data):
        return None

    # Old-style mouse: \x1b[M + 3 bytes
    if len(data) >= 4 and data.startswith("\x1b[M"):
        return None

    # Match kitty CSI-u: strip \x1b[ prefix before matching _KITTY_KEY_RE
    # (key_maps._KITTY_KEY_RE expects the CSI prefix already stripped)
    m = _KITTY_KEY_RE.match(data[2:]) if data.startswith("\x1b[") else None
    if m and use_kitty_keyboard:
        codepoint_part = m.group(1)
        modifier_part = m.group(2) or ""

        codepoint = int(codepoint_part.split(":")[0])

        mods = 0
        event_type_code = 1
        if modifier_part:
            mod_parts = modifier_part.split(":")
            mods = int(mod_parts[0]) - 1 if mod_parts[0] else 0
            if len(mod_parts) > 1:
                event_type_code = int(mod_parts[1])

        shift = bool(mods & 1)
        alt = bool(mods & 2)
        ctrl = bool(mods & 4)
        meta = bool(mods & 8)
        event_kind = "release" if event_type_code == 3 else "press"

        name = _KITTY_KEY_MAP.get(codepoint)
        if name is None:
            name = chr(codepoint) if 32 <= codepoint < 0x110000 else f"U+{codepoint:04X}"

        return KeyEvent(
            key=name,
            code=data,
            ctrl=ctrl,
            shift=shift,
            alt=alt,
            meta=meta,
            event_type=event_kind,
            sequence=chr(codepoint) if 32 <= codepoint < 0x110000 else "",
            source="kitty",
            number=name.isdigit() if len(name) == 1 else False,
        )

    if len(data) == 1 and data in _SPECIAL_CTRL:
        return KeyEvent(
            key=_SPECIAL_CTRL[data],
            code=data,
            event_type="press",
            sequence=data,
            source="raw",
        )

    if len(data) == 1 and ord(data) >= 32 and ord(data) != 127:
        return KeyEvent(
            key=data,
            code=data,
            ctrl=False,
            shift=False,
            alt=False,
            meta=False,
            event_type="press",
            sequence=data,
            source="raw",
            number=data.isdigit(),
        )

    if len(data) == 1 and "\x01" <= data <= "\x1a":
        letter = chr(ord("a") + ord(data) - 1)
        return KeyEvent(
            key=letter,
            code=data,
            ctrl=True,
            shift=False,
            alt=False,
            meta=False,
            event_type="press",
            sequence=data,
            source="raw",
        )

    if data == "\x1b":
        return KeyEvent(
            key="escape",
            code=data,
            event_type="press",
            sequence=data,
            source="raw",
        )

    if data.startswith("\x1b["):
        body = data[2:]
        arrow_map = {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end"}
        if len(body) == 1 and body in arrow_map:
            return KeyEvent(
                key=arrow_map[body],
                code=data,
                event_type="press",
                sequence=data,
                source="raw",
            )
        if body == "Z":
            return KeyEvent(
                key="tab",
                code=data,
                shift=True,
                event_type="press",
                sequence=data,
                source="raw",
            )

    return None


class KeyHandler:
    """Event-emitting key handler.

    Parses raw input via processInput() and dispatches KeyEvent/PasteEvent
    to registered listeners.
    """

    def __init__(self, use_kitty_keyboard: bool = False) -> None:
        self.use_kitty_keyboard = use_kitty_keyboard
        self._listeners: dict[str, list[Callable]] = {}

    # -- EventEmitter-like API --

    def on(self, event: str, handler: Callable) -> None:
        self._listeners.setdefault(event, []).append(handler)

    def remove_listener(self, event: str, handler: Callable) -> None:
        handlers = self._listeners.get(event)
        if handlers:
            with contextlib.suppress(ValueError):
                handlers.remove(handler)

    def remove_all_listeners(self, event: str | None = None) -> None:
        if event is None:
            self._listeners.clear()
        else:
            self._listeners.pop(event, None)

    def listeners(self, event: str) -> list[Callable]:
        return list(self._listeners.get(event, []))

    def emit(self, event: str, *args: Any) -> bool:
        """Emit an event to all registered listeners. Returns True if any exist."""
        handlers = self._listeners.get(event)
        if not handlers:
            return False
        for handler in list(handlers):
            try:
                handler(*args)
            except Exception as e:
                _log.error("[KeyHandler] Error in %s handler: %s", event, e)
            if args:
                evt = args[0]
                if hasattr(evt, "propagation_stopped") and evt.propagation_stopped:
                    return True
        return True

    # -- Public API --

    def process_input(self, data: str) -> bool:
        """Parse raw input and emit keypress/keyrelease events.

        Returns True if the input was recognized as a key event.
        """
        parsed = parse_keypress(data, use_kitty_keyboard=self.use_kitty_keyboard)
        if parsed is None:
            return False

        try:
            if parsed.event_type == "release":
                self.emit("keyrelease", parsed)
            else:
                self.emit("keypress", parsed)
        except Exception as e:
            _log.error("[KeyHandler] Error processing input: %s", e)
            return True

        return True

    def process_paste(self, data: str) -> None:
        """Process paste content: strip ANSI and emit paste event."""
        try:
            cleaned = _strip_ansi(data)
            self.emit("paste", PasteEvent(text=cleaned))
        except Exception as e:
            _log.error("[KeyHandler] Error processing paste: %s", e)


class InternalKeyHandler(KeyHandler):
    """KeyHandler with priority-based event dispatch.

    Global handlers (registered via on()) run first.
    Internal/renderable handlers (registered via on_internal()) run after,
    unless preventDefault() was called by a global handler.
    """

    def __init__(self, use_kitty_keyboard: bool = False) -> None:
        super().__init__(use_kitty_keyboard)
        self._renderable_handlers: dict[str, list[Callable]] = {}

    def on_internal(self, event: str, handler: Callable) -> None:
        self._renderable_handlers.setdefault(event, []).append(handler)

    def off_internal(self, event: str, handler: Callable) -> None:
        handlers = self._renderable_handlers.get(event)
        if handlers:
            with contextlib.suppress(ValueError):
                handlers.remove(handler)

    def emit(self, event: str, *args: Any) -> bool:
        """Emit with priority: global first, then internal."""
        return self._emit_with_priority(event, *args)

    def _emit_with_priority(self, event: str, *args: Any) -> bool:
        has_global = False
        has_internal = False

        global_listeners = self.listeners(event)
        if global_listeners:
            has_global = True
            for listener in global_listeners:
                try:
                    listener(*args)
                except Exception as e:
                    _log.error("[KeyHandler] Error in global %s handler: %s", event, e)

                # Check propagation stopped
                if args:
                    evt = args[0]
                    if hasattr(evt, "propagation_stopped") and evt.propagation_stopped:
                        return has_global

        renderable_handlers = self._renderable_handlers.get(event)
        renderable_list = list(renderable_handlers) if renderable_handlers else []

        if renderable_handlers:
            has_internal = True

            if args:
                evt = args[0]
                if hasattr(evt, "default_prevented") and evt.default_prevented:
                    return has_global or has_internal
                if hasattr(evt, "propagation_stopped") and evt.propagation_stopped:
                    return has_global or has_internal

            for handler in renderable_list:
                try:
                    handler(*args)
                except Exception as e:
                    _log.error("[KeyHandler] Error in renderable %s handler: %s", event, e)

                if args:
                    evt = args[0]
                    if hasattr(evt, "propagation_stopped") and evt.propagation_stopped:
                        return has_global or has_internal

        return has_global or has_internal


__all__ = [
    "KeyHandler",
    "InternalKeyHandler",
    "parse_keypress",
]
