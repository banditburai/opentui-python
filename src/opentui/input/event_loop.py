"""Event loop and test input handler for OpenTUI Python.

This module contains the main event loop (EventLoop) and the
test-mode input handler (TestInputHandler) that were originally
part of input.py.
"""

import contextlib
import logging
import os
from collections.abc import Callable
from typing import Any

_log = logging.getLogger(__name__)

from .handler import InputHandler

_RESIZE_DEBOUNCE = 0.10  # seconds — default resize debounce delay


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
        self._render_callbacks.append(callback)

    def run(self) -> None:
        import signal
        import time

        self._running = True
        self._input_handler.start()

        # Register SIGWINCH handler for terminal resize detection.
        # The handler sets a flag; the main loop checks it each frame
        # to avoid calling resize from a signal context.
        prev_handler = None
        with contextlib.suppress(AttributeError, OSError):
            prev_handler = signal.getsignal(signal.SIGWINCH)

        def _on_sigwinch(signum: int, frame: Any) -> None:
            self._resize_pending = True
            self._last_resize_time = time.perf_counter()

        with contextlib.suppress(AttributeError, OSError):
            signal.signal(signal.SIGWINCH, _on_sigwinch)

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
                with contextlib.suppress(AttributeError, OSError):
                    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGWINCH})
                for callback in self._render_callbacks:
                    callback(self._frame_time)
                with contextlib.suppress(AttributeError, OSError):
                    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGWINCH})

                # Sleep to maintain target FPS
                elapsed = time.perf_counter() - start_time
                sleep_time = max(0, self._frame_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            self._input_handler.stop()
            if prev_handler is not None:
                with contextlib.suppress(AttributeError, OSError):
                    signal.signal(signal.SIGWINCH, prev_handler)

    def _handle_resize(self) -> None:
        """Process a pending terminal resize.

        Called after debounce — resizes buffers, then the renderer's
        next frame does a forced full repaint at correct dimensions.
        No \x1b[2J — that pushes content into terminal scrollback.
        """
        import shutil

        from .. import hooks

        cols, lines = shutil.get_terminal_size()

        # Notify the renderer (if accessible via hooks)
        try:
            renderer = hooks.use_renderer()
            try:
                from ..image.encoding import _clear_kitty_graphics

                renderer.write_out(_clear_kitty_graphics(None))
            except Exception:
                _log.debug("failed to clear kitty graphics on resize", exc_info=True)
            renderer.resize(cols, lines)
            if renderer._root is not None:
                renderer._root._width = cols
                renderer._root._height = lines
        except RuntimeError:
            pass

        hooks._set_terminal_dimensions(cols, lines)

        for handler in hooks.get_resize_handlers():
            with contextlib.suppress(Exception):
                handler(cols, lines)

    def stop(self) -> None:
        self._running = False


class TestInputHandler(InputHandler):
    """InputHandler for test mode — reads from a pipe instead of real stdin.

    Allows injecting raw terminal sequences in tests, which flow through
    the same parsing pipeline as production input (escape sequences, mouse
    events, bracketed paste, etc.).

    Usage::

        handler = TestInputHandler()
        handler.start()
        handler.on_key(my_key_handler)
        handler.on_mouse(my_mouse_handler)
        handler.feed("\\x1b[A")  # Simulates pressing Up arrow
    """

    __test__ = False  # Not a pytest test class

    def __init__(self) -> None:
        super().__init__()
        self._pipe_r, self._pipe_w = os.pipe()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._fd = self._pipe_r

    def stop(self) -> None:
        self._running = False

    def feed(self, data: str) -> None:
        """Feed raw terminal data and process it immediately.

        Data is written to the pipe and parsed through the same pipeline
        as real terminal input.  Events are dispatched synchronously
        before this method returns.
        """
        if not data:
            return
        os.write(self._pipe_w, data.encode("utf-8"))
        while self.poll():
            pass

    def destroy(self) -> None:
        self._running = False
        for fd in (self._pipe_r, self._pipe_w):
            with contextlib.suppress(OSError):
                os.close(fd)


__all__ = [
    "EventLoop",
    "TestInputHandler",
    "_RESIZE_DEBOUNCE",
]
