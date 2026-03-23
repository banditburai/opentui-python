"""Cursor position, style, color, and software blink management."""

from __future__ import annotations

import time as _time

from .native import _CURSOR_STYLE_MAP, _CURSOR_STYLE_MAP_STEADY

# Software cursor blink interval in milliseconds (~matches typical OS blink rate).
_CURSOR_BLINK_MS = 530


class _CursorMixin:
    """Manages cursor position, style, color, and software blink.

    Expects host class to provide: _ptr, _native, _config, _cursor_request,
    _cursor_style_request, _cursor_color_request, _cursor_style, _cursor_color,
    write_out.
    """

    def set_cursor_position(self, x: int, y: int, visible: bool = True) -> None:
        self._native.renderer.set_cursor_position(self._ptr, x, y, visible)

    def request_cursor(self, x: int, y: int) -> None:
        self._cursor_request = (x, y)

    def request_cursor_style(self, style: str = "block", color: str | None = None) -> None:
        self._cursor_style_request = style
        self._cursor_color_request = color

    def _apply_cursor(self) -> None:
        """Apply (or hide) the cursor after the frame buffer is flushed.

        **Testing mode** delegates to ``set_cursor_position`` + ``write_out``
        for simple assertion-based tests.

        **Live mode** keeps the native cursor permanently hidden so that
        ``render()`` never sends ``\\x1b[?25h`` every frame (which resets
        the terminal's blink timer and prevents blinking).  Instead,
        cursor position, shape, and visibility are managed directly via
        ``sys.stdout`` with a software blink timer that toggles show/hide
        at ~530 ms intervals — matching typical OS cursor blink rates.
        """
        req = self._cursor_request
        style_req = self._cursor_style_request
        color_req = self._cursor_color_request
        self._cursor_request = None
        self._cursor_style_request = None
        self._cursor_color_request = None

        if self._config.testing:
            if req is not None:
                self.set_cursor_position(req[0] + 1, req[1] + 1, visible=True)
                style = style_req or "block"
                code = _CURSOR_STYLE_MAP.get(style, 1)
                esc = f"\x1b[{code} q"
                self._cursor_style = style
                if color_req is not None:
                    self._cursor_color = color_req
                    esc += f"\x1b]12;{color_req}\x07"
                elif self._cursor_color is not None:
                    self._cursor_color = None
                    esc += "\x1b]112\x07"
                self.write_out(esc.encode())
            else:
                self.set_cursor_position(0, 0, visible=False)
            return

        # Keep native cursor hidden so render() emits \x1b[?25l
        # (harmless no-op) instead of \x1b[?25h (which kills blink).
        self.set_cursor_position(0, 0, visible=False)

        if req is not None:
            blink_on = int(_time.monotonic() * 1000 / _CURSOR_BLINK_MS) % 2 == 0

            if blink_on:
                col = req[0] + 1
                row = req[1] + 1
                style = style_req or "block"
                # Steady DECSCUSR — shape only; blink handled by our timer.
                code = _CURSOR_STYLE_MAP_STEADY.get(style, 2)
                self._cursor_style = style

                # CUP (position) → DECSCUSR (shape) → DECTCEM (show)
                esc = f"\x1b[{row};{col}H\x1b[{code} q\x1b[?25h"

                if color_req is not None:
                    self._cursor_color = color_req
                    esc += f"\x1b]12;{color_req}\x07"
                elif self._cursor_color is not None:
                    self._cursor_color = None
                    esc += "\x1b]112\x07"

                import sys as _sys

                _sys.stdout.write(esc)
                _sys.stdout.flush()
            # blink_off: render()'s \x1b[?25l keeps cursor hidden.

    def get_cursor_state(self) -> dict:
        return self._native.renderer.get_cursor_state(self._ptr)


__all__ = ["_CursorMixin"]
