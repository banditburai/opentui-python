"""Testing utilities — SGR mouse escape-sequence generation and parsing."""

from __future__ import annotations

import re as _re
from typing import Any


# ---------------------------------------------------------------------------
# SGR mouse button constants
# ---------------------------------------------------------------------------


class _SGRMouseButtons:
    LEFT = 0
    MIDDLE = 1
    RIGHT = 2
    WHEEL_UP = 64
    WHEEL_DOWN = 65
    WHEEL_LEFT = 66
    WHEEL_RIGHT = 67


SGRMouseButtons = _SGRMouseButtons()


# ---------------------------------------------------------------------------
# SGRMockRenderer
# ---------------------------------------------------------------------------


class SGRMockRenderer:
    """Collects emitted SGR escape-sequence bytes (mock stdin)."""

    def __init__(self) -> None:
        self.emitted_data: list[str] = []

    def emit(self, data: str) -> None:
        self.emitted_data.append(data)

    def get_emitted_data(self) -> str:
        return "".join(self.emitted_data)

    def get_last_emitted_data(self) -> str:
        return self.emitted_data[-1] if self.emitted_data else ""


# ---------------------------------------------------------------------------
# SGRMockMouse
# ---------------------------------------------------------------------------


class SGRMockMouse:
    """Generates SGR mouse escape sequences and writes them to an
    ``SGRMockRenderer`` (or any object with an ``emit(str)`` method).
    """

    def __init__(self, renderer: SGRMockRenderer) -> None:
        self._renderer = renderer
        self._x = 0
        self._y = 0
        self._buttons_pressed: set[int] = set()

    # -- SGR encoding --------------------------------------------------------

    def _generate(
        self,
        event_type: str,
        x: int,
        y: int,
        button: int = 0,
        *,
        shift: bool = False,
        alt: bool = False,
        ctrl: bool = False,
    ) -> str:
        button_code = button
        if shift:
            button_code |= 4
        if alt:
            button_code |= 8
        if ctrl:
            button_code |= 16

        if event_type == "move":
            button_code = 32 | 3
            if shift:
                button_code |= 4
            if alt:
                button_code |= 8
            if ctrl:
                button_code |= 16
        elif event_type == "drag":
            first_btn = next(iter(self._buttons_pressed), button)
            button_code = first_btn | 32
            if shift:
                button_code |= 4
            if alt:
                button_code |= 8
            if ctrl:
                button_code |= 16

        ansi_x = x + 1
        ansi_y = y + 1
        suffix = "m" if event_type == "up" else "M"
        return f"\x1b[<{button_code};{ansi_x};{ansi_y}{suffix}"

    def _emit(
        self,
        event_type: str,
        x: int,
        y: int,
        button: int = 0,
        *,
        shift: bool = False,
        alt: bool = False,
        ctrl: bool = False,
    ) -> None:
        seq = self._generate(event_type, x, y, button, shift=shift, alt=alt, ctrl=ctrl)
        self._renderer.emit(seq)
        self._x, self._y = x, y
        if event_type == "down" and button < 64:
            self._buttons_pressed.add(button)
        elif event_type == "up":
            self._buttons_pressed.discard(button)

    # -- public API ----------------------------------------------------------

    def move_to(
        self, x: int, y: int, *, shift: bool = False, alt: bool = False, ctrl: bool = False
    ) -> None:
        if self._buttons_pressed:
            btn = next(iter(self._buttons_pressed))
            self._emit("drag", x, y, btn, shift=shift, alt=alt, ctrl=ctrl)
        else:
            self._emit("move", x, y, 0, shift=shift, alt=alt, ctrl=ctrl)
        self._x, self._y = x, y

    def click(
        self,
        x: int,
        y: int,
        button: int = 0,
        *,
        shift: bool = False,
        alt: bool = False,
        ctrl: bool = False,
    ) -> None:
        self._emit("down", x, y, button, shift=shift, alt=alt, ctrl=ctrl)
        self._emit("up", x, y, button, shift=shift, alt=alt, ctrl=ctrl)

    def double_click(
        self,
        x: int,
        y: int,
        button: int = 0,
        *,
        shift: bool = False,
        alt: bool = False,
        ctrl: bool = False,
    ) -> None:
        self.click(x, y, button, shift=shift, alt=alt, ctrl=ctrl)
        self.click(x, y, button, shift=shift, alt=alt, ctrl=ctrl)

    def press_down(
        self,
        x: int,
        y: int,
        button: int = 0,
        *,
        shift: bool = False,
        alt: bool = False,
        ctrl: bool = False,
    ) -> None:
        self._emit("down", x, y, button, shift=shift, alt=alt, ctrl=ctrl)

    def release(
        self,
        x: int,
        y: int,
        button: int = 0,
        *,
        shift: bool = False,
        alt: bool = False,
        ctrl: bool = False,
    ) -> None:
        self._emit("up", x, y, button, shift=shift, alt=alt, ctrl=ctrl)

    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: int = 0,
        *,
        shift: bool = False,
        alt: bool = False,
        ctrl: bool = False,
    ) -> None:
        self.press_down(start_x, start_y, button, shift=shift, alt=alt, ctrl=ctrl)
        steps = 5
        dx = (end_x - start_x) / steps
        dy = (end_y - start_y) / steps
        for i in range(1, steps + 1):
            cx = round(start_x + dx * i)
            cy = round(start_y + dy * i)
            self._emit("drag", cx, cy, button, shift=shift, alt=alt, ctrl=ctrl)
        self.release(end_x, end_y, button, shift=shift, alt=alt, ctrl=ctrl)

    def scroll(
        self,
        x: int,
        y: int,
        direction: str,
        *,
        shift: bool = False,
        alt: bool = False,
        ctrl: bool = False,
    ) -> None:
        button_map = {
            "up": SGRMouseButtons.WHEEL_UP,
            "down": SGRMouseButtons.WHEEL_DOWN,
            "left": SGRMouseButtons.WHEEL_LEFT,
            "right": SGRMouseButtons.WHEEL_RIGHT,
        }
        button = button_map[direction]
        self._emit("scroll", x, y, button, shift=shift, alt=alt, ctrl=ctrl)

    def get_current_position(self) -> dict[str, int]:
        return {"x": self._x, "y": self._y}

    def get_pressed_buttons(self) -> list[int]:
        return sorted(self._buttons_pressed)


def create_mock_mouse(
    renderer: SGRMockRenderer | None = None,
) -> tuple[SGRMockMouse, SGRMockRenderer]:
    """Create a mock mouse and renderer pair.

    Returns ``(mouse, renderer)`` — the renderer collects the SGR
    escape sequences the mouse emits.
    """
    if renderer is None:
        renderer = SGRMockRenderer()
    return SGRMockMouse(renderer), renderer


# ---------------------------------------------------------------------------
# SGR / X10 mouse sequence regexes and parser
# ---------------------------------------------------------------------------

_SGR_SEQ_RE = _re.compile(r"\x1b\[<(\d+);(\d+);(\d+)([Mm])")
# X10/normal mouse: ESC [ M <cb> <cx> <cy> — three raw bytes after "M"
_X10_SEQ_RE = _re.compile(r"\x1b\[M(.)(.)(.)", _re.DOTALL)


class SGRMouseParser:
    """Parses concatenated SGR and X10 mouse escape sequences into structured events.

    Tracks which buttons are pressed to distinguish ``drag`` from ``move``.
    """

    def __init__(self) -> None:
        self._pressed: set[int] = set()

    def reset(self) -> None:
        """Clear all tracked button state."""
        self._pressed.clear()

    def _parse_x10_event(self, button_byte: int, x: int, y: int) -> dict:
        """Parse a single X10 mouse event into an event dict."""
        shift = bool(button_byte & 4)
        alt_mod = bool(button_byte & 8)
        ctrl = bool(button_byte & 16)
        modifiers = {"shift": shift, "alt": alt_mod, "ctrl": ctrl}

        if button_byte & 64:
            # Scroll wheel
            wheel_button = button_byte & 3
            wheel_id = (button_byte & 64) | wheel_button
            direction_map = {64: "up", 65: "down", 66: "left", 67: "right"}
            direction = direction_map.get(wheel_id, "up")
            return {
                "type": "scroll",
                "button": wheel_button,
                "x": x,
                "y": y,
                "modifiers": modifiers,
                "scroll": {"direction": direction, "delta": 1},
            }
        elif button_byte & 32:
            # Motion event
            button = button_byte & 3
            event_type = "move" if button == 3 else "drag"
            return {
                "type": event_type,
                "button": button if event_type == "drag" else 0,
                "x": x,
                "y": y,
                "modifiers": modifiers,
                "scroll": None,
            }
        else:
            button = button_byte & 3
            event_type = "up" if button == 3 else "down"
            return {
                "type": event_type,
                "button": button,
                "x": x,
                "y": y,
                "modifiers": modifiers,
                "scroll": None,
            }

    def parse_all(self, data: str) -> list[dict]:
        """Parse all SGR and X10 mouse sequences in *data* and return event dicts.

        Supports both SGR (``ESC[<button;x;yM/m``) and X10/normal
        (``ESC[M<cb><cx><cy>``) mouse protocols.
        """
        events: list[dict] = []

        # Collect all matches (SGR and X10) with their positions to process in order
        matches: list[tuple[int, str, Any]] = []  # (start_pos, protocol, match_obj)

        for m in _SGR_SEQ_RE.finditer(data):
            matches.append((m.start(), "sgr", m))

        for m in _X10_SEQ_RE.finditer(data):
            matches.append((m.start(), "x10", m))

        # Sort by position so events are processed in the order they appear
        matches.sort(key=lambda t: t[0])

        for _, protocol, m in matches:
            if protocol == "sgr":
                self._process_sgr_match(m, events)
            elif protocol == "x10":
                cb = ord(m.group(1)) - 32
                cx = ord(m.group(2)) - 33  # 0-based
                cy = ord(m.group(3)) - 33
                events.append(self._parse_x10_event(cb, cx, cy))

        return events

    def _process_sgr_match(self, m: Any, events: list[dict]) -> None:
        """Process a single SGR regex match and append the event to *events*."""
        button_code = int(m.group(1))
        x = int(m.group(2)) - 1  # 1-based -> 0-based
        y = int(m.group(3)) - 1
        is_release = m.group(4) == "m"

        shift = bool(button_code & 4)
        alt_mod = bool(button_code & 8)
        ctrl = bool(button_code & 16)

        # Scroll events (bit 6)
        if button_code & 64:
            wheel_button = button_code & 3
            wheel_id = (button_code & 64) | wheel_button
            direction_map = {64: "up", 65: "down", 66: "left", 67: "right"}
            direction = direction_map.get(wheel_id, "up")
            events.append(
                {
                    "type": "scroll",
                    "button": wheel_button,
                    "x": x,
                    "y": y,
                    "modifiers": {"shift": shift, "alt": alt_mod, "ctrl": ctrl},
                    "scroll": {"direction": direction, "delta": 1},
                }
            )
        elif button_code & 32:
            # Motion event (bit 5)
            button = button_code & 3
            event_type = "move" if button == 3 or not self._pressed else "drag"
            events.append(
                {
                    "type": event_type,
                    "button": button if event_type == "drag" else 0,
                    "x": x,
                    "y": y,
                    "modifiers": {"shift": shift, "alt": alt_mod, "ctrl": ctrl},
                    "scroll": None,
                }
            )
        else:
            button = button_code & 3
            if is_release:
                self._pressed.discard(button)
                events.append(
                    {
                        "type": "up",
                        "button": button,
                        "x": x,
                        "y": y,
                        "modifiers": {"shift": shift, "alt": alt_mod, "ctrl": ctrl},
                        "scroll": None,
                    }
                )
            else:
                self._pressed.add(button)
                events.append(
                    {
                        "type": "down",
                        "button": button,
                        "x": x,
                        "y": y,
                        "modifiers": {"shift": shift, "alt": alt_mod, "ctrl": ctrl},
                        "scroll": None,
                    }
                )


# ---------------------------------------------------------------------------
# _TestStdinBridge
# ---------------------------------------------------------------------------


class _TestStdinBridge:
    """Bridge connecting MockKeys/SGRMockMouse to a TestInputHandler.

    MockKeys calls:      ``bridge.stdin.emit("data", raw_bytes)``
    SGRMockMouse calls:  ``bridge.emit(raw_bytes)``

    Both feed into ``TestInputHandler.feed()`` for full pipeline parsing.
    """

    def __init__(self, input_handler: Any) -> None:
        self._handler = input_handler
        self.stdin = self  # MockKeys uses renderer.stdin.emit(...)
        self.emitted_data: list[str] = []

    def emit(self, *args: Any) -> None:
        data = args[1] if len(args) == 2 and args[0] == "data" else args[0]
        self.emitted_data.append(data)
        self._handler.feed(data)

    def on(self, event: str, listener: Any) -> None:  # noqa: ARG002
        pass

    def write(self, data: str) -> None:
        self.emit("data", data)

    def get_emitted_data(self) -> str:
        return "".join(self.emitted_data)
