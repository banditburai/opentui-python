"""Terminal input handling for OpenTUI Python.

This module handles reading and parsing terminal input events
(keyboard, mouse) and dispatching them to the appropriate handlers.

The escape-sequence parsing state machine lives in ``_escape_parser.py``
and is mixed into ``InputHandler`` via ``EscapeParserMixin``.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..attachments import normalize_paste_payload
from ..events import KeyEvent, MouseEvent, PasteEvent
from ._escape_parser import EscapeParserMixin
from .key_maps import _ANSI_RE

if TYPE_CHECKING:
    from ._backend import TerminalBackend

_log = logging.getLogger(__name__)


class InputHandler(EscapeParserMixin):
    """Handles terminal input events."""

    def __init__(
        self,
        *,
        use_kitty_keyboard: bool = True,
        backend: TerminalBackend | None = None,
    ):
        self._backend: TerminalBackend | None = backend
        self._fd: int = -1  # kept for backward compat (Unix backend exposes fd)
        self._key_handlers: list[Callable[[KeyEvent], None]] = []
        self._mouse_handlers: list[Callable[[MouseEvent], None]] = []
        self._paste_handlers: list[Callable[[PasteEvent], None]] = []
        self._focus_handlers: list[Callable[[str], None]] = []
        self._capability_handlers: list[Callable[[dict[str, Any]], None]] = []
        self._in_bracketed_paste = False
        self._bracketed_paste_buffer = ""
        self._running = False
        self._use_kitty_keyboard = use_kitty_keyboard

    def _has_data(self, timeout: float = 0) -> bool:
        """Check if input data is available.

        Delegates to the backend. This is the single abstraction point
        that both handler.py and _escape_parser.py call.
        """
        if self._backend is None:
            return False
        return self._backend.has_data(timeout)

    def _read_char(self) -> str:
        """Read a single UTF-8 character from the backend.

        Multi-byte UTF-8 characters (e.g. Korean, Chinese, emoji) require
        reading additional continuation bytes after the leading byte:
        - 0xxxxxxx -> 1 byte  (ASCII)
        - 110xxxxx -> 2 bytes
        - 1110xxxx -> 3 bytes (CJK, most BMP)
        - 11110xxx -> 4 bytes (emoji, supplementary)
        """
        if self._backend is None:
            return ""
        b = self._backend.read_byte()
        if b < 0:
            return ""

        if b < 0x80:
            return chr(b)

        if b < 0xC0:
            remaining = 0  # Stray continuation byte
        elif b < 0xE0:
            remaining = 1  # 2-byte sequence
        elif b < 0xF0:
            remaining = 2  # 3-byte sequence (Korean, Chinese, etc.)
        elif b < 0xF8:
            remaining = 3  # 4-byte sequence (emoji)
        else:
            remaining = 0  # Invalid leading byte

        data = bytes([b])
        for _ in range(remaining):
            if not self._has_data(0.05):
                break
            extra_b = self._backend.read_byte()
            if extra_b < 0:
                break
            data += bytes([extra_b])

        return data.decode("utf-8", errors="replace")

    # -- Lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self._backend is None:
            from ._backend import create_backend

            self._backend = create_backend()
        self._backend.start()
        # Expose fd for backward compat (Unix backend has it)
        if hasattr(self._backend, "fd"):
            self._fd = self._backend.fd

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._backend is not None:
            self._backend.stop()

    # -- Handler registration ------------------------------------------------

    def on_key(self, handler: Callable[[KeyEvent], None]) -> None:
        self._key_handlers.append(handler)

    def on_mouse(self, handler: Callable[[MouseEvent], None]) -> None:
        self._mouse_handlers.append(handler)

    def on_paste(self, handler: Callable[[PasteEvent], None]) -> None:
        self._paste_handlers.append(handler)

    def on_focus(self, handler: Callable[[str], None]) -> None:
        """Register a focus event handler.

        Handler receives "focus" or "blur" as the argument.
        """
        self._focus_handlers.append(handler)

    def on_capability(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a capability response handler.

        Handler receives a dict describing the capability response, e.g.:
        ``{"type": "decrpm", "mode": 1016, "value": 2}``
        ``{"type": "xtversion", "name": "kitty", "version": "0.40.1"}``
        ``{"type": "kitty_graphics", "supported": True}``
        ``{"type": "da1", "params": [62]}``
        ``{"type": "kitty_keyboard", "flags": 0}``
        ``{"type": "cpr", "row": 1, "col": 2}``
        """
        self._capability_handlers.append(handler)

    # -- Main dispatch loop --------------------------------------------------

    def poll(self) -> bool:
        if not self._running:
            return False

        if self._has_data(0):
            char = self._read_char()
            if not char:
                return False

            if self._in_bracketed_paste:
                self._consume_bracketed_paste_char(char)
                return True

            if char == "\x1b":
                return self._handle_escape()
            elif char == "\r":
                self._emit_key("return", char, sequence=char)
            elif char == "\n":
                # LF is "linefeed" — distinct from CR ("return"), matching
                # OpenTUI core key parsing which maps LF to key "linefeed".
                self._emit_key("linefeed", char, sequence=char)
            elif char == "\t":
                self._emit_key("tab", char, sequence=char)
            elif char == "\x00":  # NUL = Ctrl+Space
                self._emit_key("space", char, ctrl=True, sequence=char)
            elif char in {"\x7f", "\x08"}:
                self._emit_key("backspace", char, sequence=char)
            elif "\x01" <= char <= "\x1a":  # Ctrl+A through Ctrl+Z
                letter = chr(ord("a") + ord(char) - 1)
                self._emit_key(letter, char, ctrl=True, sequence=char)
            else:
                _log.debug("input raw char=%r U+%04X", char, ord(char))
                self._emit_key(char, char, sequence=char)

            return True

        return False

    # -- Event emitters ------------------------------------------------------

    def _emit_key(
        self,
        key: str,
        code: str,
        ctrl: bool = False,
        shift: bool = False,
        alt: bool = False,
        meta: bool = False,
        sequence: str = "",
        source: str = "raw",
    ) -> None:
        is_digit = len(key) == 1 and key.isdigit()
        event = KeyEvent(
            key=key,
            code=code,
            ctrl=ctrl,
            shift=shift,
            alt=alt,
            meta=meta,
            repeated=False,
            sequence=sequence,
            source=source,
            number=is_digit,
        )

        for handler in self._key_handlers:
            handler(event)
            if event.propagation_stopped:
                break

    def _emit_mouse(self, event: MouseEvent) -> None:
        for handler in self._mouse_handlers:
            handler(event)
            if event.propagation_stopped:
                break

    def _emit_focus(self, focus_type: str) -> None:
        """Emit a focus event (focus-in or focus-out).

        Focus events are NOT keyboard events — they are dispatched to
        registered focus handlers and should not reach key handlers.
        """
        for handler in self._focus_handlers:
            with contextlib.suppress(Exception):
                handler(focus_type)

    def _emit_capability(self, cap: dict[str, Any]) -> None:
        """Emit a capability response event.

        Called when the terminal sends a response to a capability query
        (DECRPM, XTVersion, Kitty graphics, DA1, Kitty keyboard, CPR).
        """
        for handler in self._capability_handlers:
            with contextlib.suppress(Exception):
                handler(cap)

    def _emit_paste(self, text: str) -> None:
        text = _ANSI_RE.sub("", text)
        event = normalize_paste_payload(text)
        for handler in self._paste_handlers:
            handler(event)
            if event.propagation_stopped:
                break


__all__ = [
    "InputHandler",
]
