"""Terminal input handling for OpenTUI Python.

This module handles reading and parsing terminal input events
(keyboard, mouse) and dispatching them to the appropriate handlers.
"""

from __future__ import annotations

import os
import select
import sys
import termios
import tty
from collections.abc import Callable
from typing import Any

from .events import KeyEvent, MouseButton, MouseEvent, PasteEvent


class InputHandler:
    """Handles terminal input events."""

    def __init__(self):
        self._old_settings: Any = None
        self._fd: int = -1  # raw fd for unbuffered reads
        self._key_handlers: list[Callable[[KeyEvent], None]] = []
        self._mouse_handlers: list[Callable[[MouseEvent], None]] = []
        self._paste_handlers: list[Callable[[PasteEvent], None]] = []
        self._running = False

    def _read_char(self) -> str:
        """Read a single byte from the terminal fd, bypassing Python's buffer.

        Using os.read() on the raw fd prevents the select/read mismatch
        that occurs with sys.stdin.read(1): Python's BufferedReader may
        pre-read more bytes from the fd into its internal buffer, causing
        subsequent select() calls to report "no data" even though Python's
        buffer holds the remaining bytes of an escape sequence.
        """
        data = os.read(self._fd, 1)
        return data.decode("utf-8", errors="replace") if data else ""

    def start(self) -> None:
        """Start reading input."""
        if self._running:
            return
        self._running = True
        self._fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        # Disable ISIG so Ctrl+C delivers \x03 byte to stdin instead of
        # raising SIGINT.  This lets the key handler process it cleanly
        # without asyncio's signal handler interfering with shutdown.
        new_settings = termios.tcgetattr(self._fd)
        new_settings[3] &= ~termios.ISIG  # lflags
        termios.tcsetattr(self._fd, termios.TCSANOW, new_settings)

    def stop(self) -> None:
        """Stop reading input and restore terminal."""
        if not self._running:
            return
        self._running = False
        if self._old_settings:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
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

        # Use select on the raw fd (not sys.stdin) to avoid mismatch
        # with os.read — both now operate on the kernel buffer directly.
        if select.select([self._fd], [], [], 0)[0]:
            char = self._read_char()
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
        if not select.select([self._fd], [], [], 0)[0]:
            # Just ESC pressed
            self._emit_key("escape", "\x1b")
            return True

        char = self._read_char()
        if char == "[":
            # CSI sequence
            return self._handle_csi()
        elif char == "O":
            # SS3 sequence
            return self._handle_ss3()
        elif char == "P":
            # DCS (Device Control String) — e.g. Ghostty's `\x1bP>|ghostty 1.3.0\x1b\\`
            # Consume until ST (String Terminator: \x1b\\ or \x9c)
            self._consume_until_st()
            return True
        elif char == "]":
            # OSC (Operating System Command) — consume until ST
            self._consume_until_st()
            return True

        self._emit_key("escape", "\x1b")
        return True

    def _consume_until_st(self) -> None:
        """Consume bytes until String Terminator (ESC \\ or 0x9c).

        Used to silently discard DCS, OSC, and other escape sequences
        that the terminal sends as responses to capability queries.
        """
        prev = ""
        while select.select([self._fd], [], [], 0.05)[0]:
            ch = self._read_char()
            if ch == "\x9c":
                return  # 8-bit ST
            if prev == "\x1b" and ch == "\\":
                return  # 7-bit ST (ESC \\)
            prev = ch

    def _handle_csi(self) -> bool:
        """Handle CSI (Control Sequence Introducer) escape sequences."""
        if not select.select([self._fd], [], [], 0)[0]:
            self._emit_key("[", "\x1b[")
            return True

        seq = ""
        while True:
            char = self._read_char()
            seq += char
            # SGR mouse ends with 'M' or 'm'; normal CSI ends with alpha or '~'
            if char.isalpha() or char == "~":
                break

        # SGR mouse protocol: \x1b[<button;x;y;M (press) or m (release)
        if seq.startswith("<") and (seq.endswith("M") or seq.endswith("m")):
            return self._handle_sgr_mouse(seq)

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

    def _handle_sgr_mouse(self, seq: str) -> bool:
        """Handle SGR mouse protocol: \x1b[<button;x;y;M/m

        Button encoding (low 2 bits = button, higher bits = modifiers):
            0 = left, 1 = middle, 2 = right
            +4 = shift, +8 = meta/alt, +16 = ctrl
            64 = wheel up, 65 = wheel down
        M = press, m = release
        """
        is_release = seq.endswith("m")
        # Strip leading '<' and trailing 'M'/'m'
        params = seq[1:-1]
        try:
            parts = params.split(";")
            button_code = int(parts[0])
            x = int(parts[1]) - 1  # SGR uses 1-based coordinates
            y = int(parts[2]) - 1
        except (ValueError, IndexError):
            return True

        # Decode modifiers from button code
        shift = bool(button_code & 4)
        alt = bool(button_code & 8)
        ctrl = bool(button_code & 16)

        # Check for scroll wheel (bit 6 set = 64)
        if button_code & 64:
            direction = button_code & 1  # 0 = up, 1 = down
            scroll_delta = 1 if direction else -1
            self._emit_mouse(MouseEvent(
                type="scroll",
                x=x, y=y,
                button=MouseButton.WHEEL_UP if direction == 0 else MouseButton.WHEEL_DOWN,
                scroll_delta=scroll_delta,
                shift=shift, ctrl=ctrl, alt=alt,
            ))
        else:
            # Regular button
            button = button_code & 3  # 0=left, 1=middle, 2=right
            if button_code & 32:
                event_type = "drag"
            elif is_release:
                event_type = "up"
            else:
                event_type = "down"
            self._emit_mouse(MouseEvent(
                type=event_type,
                x=x, y=y,
                button=button,
                shift=shift, ctrl=ctrl, alt=alt,
            ))

        return True

    def _handle_ss3(self) -> bool:
        """Handle SS3 (Single Shift 3) escape sequences."""
        if not select.select([self._fd], [], [], 0)[0]:
            self._emit_key("O", "\x1bO")
            return True

        char = self._read_char()

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
            if event.propagation_stopped:
                break

    def _emit_mouse(self, event: MouseEvent) -> None:
        """Emit a mouse event."""
        for handler in self._mouse_handlers:
            handler(event)
            if event.propagation_stopped:
                break

    def _emit_paste(self, text: str) -> None:
        """Emit a paste event."""
        event = PasteEvent(text=text)
        for handler in self._paste_handlers:
            handler(event)
            if event.propagation_stopped:
                break


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


_RESIZE_DEBOUNCE = 0.10  # seconds — matches OpenCode's resizeDebounceDelay


class EventLoop:
    """Main event loop for the terminal application."""

    def __init__(self, target_fps: float = 60.0):
        self._input_handler = InputHandler()
        self._target_fps = target_fps
        self._frame_time = 1.0 / target_fps
        self._running = False
        self._render_callbacks: list[Callable[[float], None]] = []
        self._resize_pending = False
        self._last_resize_time: float = 0.0

    @property
    def input_handler(self) -> InputHandler:
        return self._input_handler

    def on_frame(self, callback: Callable[[float], None]) -> None:
        """Register a frame callback (for rendering)."""
        self._render_callbacks.append(callback)

    def run(self) -> None:
        """Run the event loop."""
        import signal
        import time

        self._running = True
        self._input_handler.start()

        # Register SIGWINCH handler for terminal resize detection.
        # The handler sets a flag; the main loop checks it each frame
        # to avoid calling resize from a signal context.
        prev_handler = None
        try:
            prev_handler = signal.getsignal(signal.SIGWINCH)
        except (AttributeError, OSError):
            pass  # SIGWINCH not available on this platform

        def _on_sigwinch(signum: int, frame: Any) -> None:
            self._resize_pending = True
            self._last_resize_time = time.perf_counter()

        try:
            signal.signal(signal.SIGWINCH, _on_sigwinch)
        except (AttributeError, OSError):
            pass

        try:
            while self._running:
                start_time = time.perf_counter()

                # Resize handling — debounce 100ms after last SIGWINCH.
                #
                # ALWAYS keep rendering during debounce (at old dims).
                # The native renderer wraps each frame in DEC Synced
                # Output (CSI ?2026h … CSI ?2026l), so the terminal
                # shows each frame atomically.  Between frames the
                # terminal may briefly reflow, but the next atomic
                # frame overwrites everything within ~16ms.
                #
                # After debounce: resize buffers → force full repaint
                # at correct dimensions.  No \x1b[2J — that pushes
                # alternate-screen content into terminal scrollback.
                if self._resize_pending:
                    since_last = time.perf_counter() - self._last_resize_time
                    if since_last >= _RESIZE_DEBOUNCE:
                        self._resize_pending = False
                        self._handle_resize()

                # Drain ALL pending input events before rendering.
                while self._input_handler.poll():
                    pass

                # ALWAYS render — block SIGWINCH during render so it
                # can't fire mid-flush and cause a dimension mismatch.
                try:
                    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGWINCH})
                except (AttributeError, OSError):
                    pass
                for callback in self._render_callbacks:
                    callback(self._frame_time)
                try:
                    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGWINCH})
                except (AttributeError, OSError):
                    pass

                # Sleep to maintain target FPS
                elapsed = time.perf_counter() - start_time
                sleep_time = max(0, self._frame_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            self._input_handler.stop()
            # Restore previous SIGWINCH handler
            if prev_handler is not None:
                try:
                    signal.signal(signal.SIGWINCH, prev_handler)
                except (AttributeError, OSError):
                    pass

    def _handle_resize(self) -> None:
        """Process a pending terminal resize.

        Called after debounce — resizes buffers, then the renderer's
        next frame does a forced full repaint at correct dimensions.
        No \x1b[2J — that pushes content into terminal scrollback.
        """
        import shutil

        from . import hooks

        cols, lines = shutil.get_terminal_size()

        # Notify the renderer (if accessible via hooks)
        try:
            renderer = hooks.use_renderer()
            renderer.resize(cols, lines)
            # Update root renderable dimensions
            if renderer._root is not None:
                renderer._root._width = cols
                renderer._root._height = lines
        except RuntimeError:
            pass

        hooks._set_terminal_dimensions(cols, lines)

        # Notify resize handlers
        for handler in hooks.get_resize_handlers():
            try:
                handler(cols, lines)
            except Exception:
                pass

    def stop(self) -> None:
        """Stop the event loop."""
        self._running = False


__all__ = [
    "InputHandler",
    "EventLoop",
]
