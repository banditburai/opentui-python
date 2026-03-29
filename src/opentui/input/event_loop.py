"""Event loop and test input handler for OpenTUI Python.

This module contains the main event loop (EventLoop) and the
test-mode input handler (TestInputHandler) that were originally
part of input.py.
"""

import contextlib
import logging
from collections.abc import Callable
from typing import Any

_log = logging.getLogger(__name__)

from ._backend_buffer import BufferBackend
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

        has_sigwinch = hasattr(signal, "SIGWINCH")

        # Register SIGWINCH handler for terminal resize detection (Unix only).
        # The handler sets a flag; the main loop checks it each frame
        # to avoid calling resize from a signal context.
        prev_handler = None
        if has_sigwinch:
            with contextlib.suppress(AttributeError, OSError):
                prev_handler = signal.getsignal(signal.SIGWINCH)

            def _on_sigwinch(signum: int, frame: Any) -> None:
                self._resize_pending = True
                self._last_resize_time = time.perf_counter()

            with contextlib.suppress(AttributeError, OSError):
                signal.signal(signal.SIGWINCH, _on_sigwinch)

        # Polling resize fallback for platforms without SIGWINCH (Windows)
        if not has_sigwinch:
            import shutil

            self._last_term_size = shutil.get_terminal_size()

        try:
            while self._running:
                start_time = time.perf_counter()

                if has_sigwinch:
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
                else:
                    # Polling fallback: check terminal size each frame
                    import shutil

                    current_size = shutil.get_terminal_size()
                    if current_size != self._last_term_size:
                        self._last_term_size = current_size
                        self._handle_resize()

                # Drain ALL pending input events before rendering.
                while self._input_handler.poll():
                    pass

                # ALWAYS render — block SIGWINCH during render so it
                # can't fire mid-flush and cause a dimension mismatch.
                if has_sigwinch:
                    with contextlib.suppress(AttributeError, OSError):
                        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGWINCH})
                for callback in self._render_callbacks:
                    callback(self._frame_time)
                if has_sigwinch:
                    with contextlib.suppress(AttributeError, OSError):
                        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGWINCH})

                # Sleep to maintain target FPS
                elapsed = time.perf_counter() - start_time
                sleep_time = max(0, self._frame_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            self._input_handler.stop()
            if has_sigwinch and prev_handler is not None:
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
    """InputHandler for test mode — reads from a buffer instead of real stdin.

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
        self._buffer_backend = BufferBackend()
        super().__init__(backend=self._buffer_backend)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._backend.start()  # type: ignore[union-attr]

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._backend.stop()  # type: ignore[union-attr]

    def feed(self, data: str) -> None:
        """Feed raw terminal data and process it immediately.

        Data is written to the buffer backend and parsed through the same
        pipeline as real terminal input.  Events are dispatched synchronously
        before this method returns.
        """
        if not data:
            return
        self._buffer_backend.feed(data)
        while self.poll():
            pass

    def destroy(self) -> None:
        self._running = False


__all__ = [
    "EventLoop",
    "TestInputHandler",
    "_RESIZE_DEBOUNCE",
]
