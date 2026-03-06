"""Terminal input handling for OpenTUI Python.

This module handles reading and parsing terminal input events
(keyboard, mouse) and dispatching them to the appropriate handlers.
"""

from __future__ import annotations

import select
import sys
import termios
import tty
from collections.abc import Callable
from typing import Any

from .events import KeyEvent, MouseEvent, PasteEvent


class InputHandler:
    """Handles terminal input events."""

    def __init__(self):
        self._old_settings: Any = None
        self._key_handlers: list[Callable[[KeyEvent], None]] = []
        self._mouse_handlers: list[Callable[[MouseEvent], None]] = []
        self._paste_handlers: list[Callable[[PasteEvent], None]] = []
        self._running = False

    def start(self) -> None:
        """Start reading input."""
        if self._running:
            return
        self._running = True
        self._old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

    def stop(self) -> None:
        """Stop reading input and restore terminal."""
        if not self._running:
            return
        self._running = False
        if self._old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
            self._old_settings = None

    def on_key(self, handler: Callable[[KeyEvent], None]) -> None:
        """Register a keyboard event handler."""
        self._key_handlers.append(handler)

    def on_mouse(self, handler: Callable[[MouseEvent], None]) -> None:
        """Register a mouse event handler."""
        self._mouse_handlers.append(handler)

    def on_paste(self, handler: Callable[[PasteEvent], None]) -> None:
        """Register a paste event handler."""
        self._paste_handlers.append(handler)

    def poll(self) -> bool:
        """Poll for input. Returns True if input was processed."""
        if not self._running:
            return False

        # Use select for non-blocking read
        if select.select([sys.stdin], [], [], 0)[0]:
            char = sys.stdin.read(1)
            if not char:
                return False

            # Check for escape sequences
            if char == "\x1b":  # ESC
                return self._handle_escape()
            elif char == "\r" or char == "\n":
                self._emit_key("return", char)
            elif char == "\t":
                self._emit_key("tab", char)
            elif char == "\x7f":  # DEL
                self._emit_key("backspace", char)
            elif char == "\x03":  # Ctrl+C
                self._emit_key("c", char, ctrl=True)
            elif char == "\x04":  # Ctrl+D
                self._emit_key("d", char, ctrl=True)
            else:
                self._emit_key(char, char)

            return True

        return False

    def _handle_escape(self) -> bool:
        """Handle escape sequence."""
        if not select.select([sys.stdin], [], [], 0)[0]:
            # Just ESC pressed
            self._emit_key("escape", "\x1b")
            return True

        char = sys.stdin.read(1)
        if char == "[":
            # CSI sequence
            return self._handle_csi()
        elif char == "O":
            # SS3 sequence
            return self._handle_ss3()

        self._emit_key("escape", "\x1b")
        return True

    def _handle_csi(self) -> bool:
        """Handle CSI (Control Sequence Introducer) escape sequences."""
        if not select.select([sys.stdin], [], [], 0)[0]:
            self._emit_key("[", "\x1b[")
            return True

        seq = ""
        while True:
            char = sys.stdin.read(1)
            seq += char
            if char.isalpha() or char == "~":
                break

        # Parse CSI sequence
        if seq == "A":
            self._emit_key("up", f"\x1b[{seq}")
        elif seq == "B":
            self._emit_key("down", f"\x1b[{seq}")
        elif seq == "C":
            self._emit_key("right", f"\x1b[{seq}")
        elif seq == "D":
            self._emit_key("left", f"\x1b[{seq}")
        elif seq == "H":
            self._emit_key("home", f"\x1b[{seq}")
        elif seq == "F":
            self._emit_key("end", f"\x1b[{seq}")
        elif seq == "P":
            self._emit_key("f1", f"\x1b[{seq}")
        elif seq == "Q":
            self._emit_key("f2", f"\x1b[{seq}")
        elif seq == "R":
            self._emit_key("f3", f"\x1b[{seq}")
        elif seq == "S":
            self._emit_key("f4", f"\x1b[{seq}")
        elif seq.startswith("1") and seq.endswith("~"):
            # Home, Insert, etc.
            self._emit_key(_csi_num_to_key(int(seq[1:-1])), f"\x1b[{seq}")
        elif seq.startswith("2") and seq.endswith("~"):
            self._emit_key(_csi_num_to_key(int(seq[1:-1])), f"\x1b[{seq}")
        elif seq.startswith("3") and seq.endswith("~"):
            self._emit_key(_csi_num_to_key(int(seq[1:-1])), f"\x1b[{seq}")
        elif seq.startswith("5") and seq.endswith("~"):
            self._emit_key("pageup", f"\x1b[{seq}")
        elif seq.startswith("6") and seq.endswith("~"):
            self._emit_key("pagedown", f"\x1b[{seq}")
        else:
            self._emit_key(f"unknown-{seq}", f"\x1b[{seq}")

        return True

    def _handle_ss3(self) -> bool:
        """Handle SS3 (Single Shift 3) escape sequences."""
        if not select.select([sys.stdin], [], [], 0)[0]:
            self._emit_key("O", "\x1bO")
            return True

        char = sys.stdin.read(1)

        if char == "P":
            self._emit_key("f1", f"\x1bO{char}")
        elif char == "Q":
            self._emit_key("f2", f"\x1bO{char}")
        elif char == "R":
            self._emit_key("f3", f"\x1bO{char}")
        elif char == "S":
            self._emit_key("f4", f"\x1bO{char}")
        elif char == "H":
            self._emit_key("home", f"\x1bO{char}")
        elif char == "F":
            self._emit_key("end", f"\x1bO{char}")
        else:
            self._emit_key(f"ss3-{char}", f"\x1bO{char}")

        return True

    def _emit_key(
        self,
        key: str,
        code: str,
        ctrl: bool = False,
        shift: bool = False,
        alt: bool = False,
        meta: bool = False,
    ) -> None:
        """Emit a keyboard event."""
        event = KeyEvent(
            key=key,
            code=code,
            ctrl=ctrl,
            shift=shift,
            alt=alt,
            meta=meta,
            repeated=False,
        )

        for handler in self._key_handlers:
            handler(event)

    def _emit_mouse(self, event: MouseEvent) -> None:
        """Emit a mouse event."""
        for handler in self._mouse_handlers:
            handler(event)

    def _emit_paste(self, text: str) -> None:
        """Emit a paste event."""
        event = PasteEvent(text=text)
        for handler in self._paste_handlers:
            handler(event)


def _csi_num_to_key(num: int) -> str:
    """Convert CSI sequence number to key name."""
    mapping = {
        1: "home",
        2: "insert",
        3: "delete",
        4: "end",
        5: "pageup",
        6: "pagedown",
        7: "home",
        8: "end",
    }
    return mapping.get(num, f"unknown-{num}")


class EventLoop:
    """Main event loop for the terminal application."""

    def __init__(self, target_fps: float = 60.0):
        self._input_handler = InputHandler()
        self._target_fps = target_fps
        self._frame_time = 1.0 / target_fps
        self._running = False
        self._render_callbacks: list[Callable[[float], None]] = []

    @property
    def input_handler(self) -> InputHandler:
        return self._input_handler

    def on_frame(self, callback: Callable[[float], None]) -> None:
        """Register a frame callback (for rendering)."""
        self._render_callbacks.append(callback)

    def run(self) -> None:
        """Run the event loop."""
        self._running = True
        self._input_handler.start()

        try:
            import time

            while self._running:
                start_time = time.perf_counter()

                # Poll for input
                self._input_handler.poll()

                # Render frame
                for callback in self._render_callbacks:
                    callback(self._frame_time)

                # Sleep to maintain target FPS
                elapsed = time.perf_counter() - start_time
                sleep_time = max(0, self._frame_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            self._input_handler.stop()

    def stop(self) -> None:
        """Stop the event loop."""
        self._running = False


__all__ = [
    "InputHandler",
    "EventLoop",
]
