"""Terminal session helpers for CliRenderer."""

from __future__ import annotations

import contextlib
import logging
import time as _time
from typing import Any

from .. import hooks

_log = logging.getLogger(__name__)


def prepare_terminal_session(renderer: Any) -> tuple[Any, Any, Any]:
    import os as _os
    import select as _sel
    import sys as _sys
    import termios as _termios

    fd = _sys.stdin.fileno()
    pre_attrs = _disable_echo(fd, _termios)
    renderer.setup()
    if not renderer._config.testing and renderer._config.kitty_keyboard_flags:
        with contextlib.suppress(Exception):
            renderer.enable_keyboard(renderer._config.kitty_keyboard_flags)
    _drain_startup_stdin(fd, _os, _sel)
    if pre_attrs is not None:
        with contextlib.suppress(OSError, _termios.error):
            _termios.tcsetattr(fd, _termios.TCSANOW, pre_attrs)
    return _os, _sel, _sys


def bind_event_loop(renderer: Any, event_loop: Any) -> None:
    input_handler = event_loop.input_handler

    for event_type, handlers in renderer._get_event_forwarding().items():
        if event_type == "key":
            for handler in handlers:
                input_handler.on_key(handler)
        elif event_type == "paste":
            for handler in handlers:
                input_handler.on_paste(handler)

    for handler in hooks.get_keyboard_handlers():
        input_handler.on_key(handler)
    for handler in hooks.get_paste_handlers():
        input_handler.on_paste(handler)

    renderer._should_restore_modes = False

    def _on_focus(focus_type: str) -> None:
        if focus_type == "blur":
            renderer._should_restore_modes = True
            renderer.emit_event("blur")
        elif focus_type == "focus":
            if renderer._should_restore_modes:
                renderer._should_restore_modes = False
                restore_terminal_modes(renderer)
            renderer.emit_event("focus")

    input_handler.on_focus(_on_focus)
    for handler in hooks.get_focus_handlers():
        input_handler.on_focus(handler)

    input_handler.on_mouse(renderer._dispatch_mouse_event)
    for handler in hooks.get_mouse_handlers():
        input_handler.on_mouse(handler)

    renderer._refresh_mouse_tracking()
    event_loop.on_frame(renderer._render_frame)


def restore_terminal_modes(renderer: Any) -> None:
    if renderer._config.testing:
        return
    try:
        import sys as _sys

        buf = ""
        if renderer._config.kitty_keyboard_flags:
            renderer.enable_keyboard(renderer._config.kitty_keyboard_flags)
        if renderer._mouse_enabled:
            renderer.enable_mouse()
        buf += "\x1b[?2004h"
        _sys.stdout.write(buf)
        _sys.stdout.flush()
    except Exception:
        _log.debug("Failed to restore terminal modes on focus", exc_info=True)


def teardown_terminal_session(renderer: Any, *, os_module: Any, select_module: Any, sys_module: Any) -> None:
    with contextlib.suppress(Exception):
        renderer.disable_keyboard()
    with contextlib.suppress(Exception):
        sys_module.stdout.write("\x1b[0 q\x1b]112\x07")
        sys_module.stdout.flush()
    try:
        fd = sys_module.stdin.fileno()
        for _ in range(3):
            _time.sleep(0.03)
            while select_module.select([fd], [], [], 0.02)[0]:
                os_module.read(fd, 4096)
    except (OSError, ValueError):
        pass


def destroy_terminal_session(renderer: Any) -> None:
    if renderer._root is not None:
        renderer._root.destroy()
        renderer._root = None
    renderer._current_mouse_pointer_style = "default"
    renderer._last_over_renderable = None
    if renderer._palette_detector is not None:
        renderer._palette_detector.cleanup()
        renderer._palette_detector = None
    renderer._palette_detection_promise = None
    renderer._cached_palette = None
    if renderer._ptr:
        renderer._native.renderer.destroy_renderer(renderer._ptr)
        renderer._ptr = None
    renderer._running = False
    renderer._force_resolve_idle_futures()


def _disable_echo(fd: int, termios_module: Any) -> Any | None:
    try:
        pre_attrs = termios_module.tcgetattr(fd)
        noecho = termios_module.tcgetattr(fd)
        noecho[3] &= ~termios_module.ECHO
        termios_module.tcsetattr(fd, termios_module.TCSANOW, noecho)
        return pre_attrs
    except (OSError, termios_module.error):
        return None


def _drain_startup_stdin(fd: int, os_module: Any, select_module: Any) -> None:
    drain_deadline = 0.4
    drain_idle = 0.08
    deadline = _time.perf_counter() + drain_deadline
    last_data = _time.perf_counter()
    while _time.perf_counter() < deadline:
        remaining = min(deadline - _time.perf_counter(), drain_idle)
        if remaining <= 0:
            break
        if select_module.select([fd], [], [], remaining)[0]:
            os_module.read(fd, 4096)
            last_data = _time.perf_counter()
        elif _time.perf_counter() - last_data >= drain_idle:
            break


__all__ = [
    "bind_event_loop",
    "destroy_terminal_session",
    "prepare_terminal_session",
    "restore_terminal_modes",
    "teardown_terminal_session",
]
