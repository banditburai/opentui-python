"""Testing utilities for OpenTUI Python — BufferDiff, MockInput, MockMouse."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from . import hooks
from .events import KeyEvent, Keys, MouseButton, MouseEvent

if TYPE_CHECKING:
    from . import TestSetup


DiffType = Literal["line_count", "text", "width"]


class DiffResult:
    def __init__(
        self,
        type: DiffType,
        message: str,
        line: int | None = None,
        expected: str | None = None,
        actual: str | None = None,
    ):
        self.type = type
        self.message = message
        self.line = line
        self.expected = expected
        self.actual = actual


class BufferDiff:
    """Utility for comparing buffer outputs between implementations."""

    def __init__(self, expected: list[dict], actual: list[dict]):
        self.expected = expected
        self.actual = actual
        self.differences: list[DiffResult] = []

    def compare(self) -> list[DiffResult]:
        """Compare expected and actual buffers."""
        self.differences = []

        if len(self.expected) != len(self.actual):
            self.differences.append(
                DiffResult(
                    type="line_count",
                    message=f"Line count mismatch: expected {len(self.expected)}, got {len(self.actual)}",
                )
            )
            return self.differences

        for y, (exp_line, act_line) in enumerate(zip(self.expected, self.actual, strict=False)):
            exp_text = exp_line.get("text", "")
            act_text = act_line.get("text", "")

            if exp_text != act_text:
                self.differences.append(
                    DiffResult(
                        type="text",
                        message=f"Line {y} text mismatch",
                        line=y,
                        expected=exp_text,
                        actual=act_text,
                    )
                )

            exp_width = exp_line.get("width", len(exp_text))
            act_width = act_line.get("width", len(act_text))

            if exp_width != act_width:
                self.differences.append(
                    DiffResult(
                        type="width",
                        message=f"Line {y} width mismatch: expected {exp_width}, got {act_width}",
                        line=y,
                        expected=str(exp_width),
                        actual=str(act_width),
                    )
                )

        return self.differences

    def has_differences(self) -> bool:
        """Check if there are any differences."""
        return len(self.differences) > 0

    def summary(self) -> str:
        """Get a summary of differences."""
        if not self.differences:
            return "No differences found"

        lines = [f"Found {len(self.differences)} difference(s):"]
        for diff in self.differences:
            lines.append(f"  - {diff.message}")
        return "\n".join(lines)


def assert_buffer_equal(expected: list[dict], actual: list[dict]) -> None:
    """Assert that two buffers are equal, raise on difference."""
    diff = BufferDiff(expected, actual)
    differences = diff.compare()

    if differences:
        raise AssertionError(diff.summary())


# ---------------------------------------------------------------------------
# MockInput
# ---------------------------------------------------------------------------


class MockInput:
    """Simulate keyboard / paste input for tests."""

    def __init__(self, setup: TestSetup) -> None:
        self._setup = setup

    # -- core dispatch -------------------------------------------------------

    def press_key(
        self,
        key: str,
        *,
        ctrl: bool = False,
        shift: bool = False,
        alt: bool = False,
        meta: bool = False,
    ) -> None:
        """Create a KeyEvent and dispatch to registered keyboard handlers."""
        event = KeyEvent(
            key=key,
            code=key,
            ctrl=ctrl,
            shift=shift,
            alt=alt,
            meta=meta,
        )
        for handler in hooks.get_keyboard_handlers():
            if event.propagation_stopped:
                break
            handler(event)

    def press_keys(self, keys: list[str]) -> None:
        """Press multiple keys in sequence."""
        for key in keys:
            self.press_key(key)

    def type_text(self, text: str) -> None:
        """Type text — one key event per character."""
        for ch in text:
            self.press_key(ch)

    # -- convenience ---------------------------------------------------------

    def press_enter(self) -> None:
        self.press_key(Keys.RETURN)

    def press_escape(self) -> None:
        self.press_key(Keys.ESCAPE)

    def press_tab(self) -> None:
        self.press_key(Keys.TAB)

    def press_backspace(self) -> None:
        self.press_key(Keys.BACKSPACE)

    def press_arrow(self, direction: str) -> None:
        """Press an arrow key.  *direction*: ``"up"``, ``"down"``, ``"left"``, ``"right"``."""
        arrow_map = {"up": Keys.UP, "down": Keys.DOWN, "left": Keys.LEFT, "right": Keys.RIGHT}
        key = arrow_map.get(direction)
        if key is None:
            raise ValueError(f"Invalid arrow direction: {direction!r}")
        self.press_key(key)

    def press_ctrl_c(self) -> None:
        self.press_key("c", ctrl=True)

    # -- paste ---------------------------------------------------------------

    def paste_text(self, text: str) -> None:
        """Dispatch text to paste handlers."""
        from .attachments import normalize_paste_payload

        event = normalize_paste_payload(text)
        for handler in hooks.get_paste_handlers():
            handler(event)

    def paste_bracketed_text(self, text: str) -> None:
        """Send text via bracketed paste mode through the full input pipeline.

        Feeds ``ESC[200~`` + *text* + ``ESC[201~`` into the stdin-level
        ``TestInputHandler`` so the paste goes through the same parsing
        path as real terminal bracketed paste.
        """
        self._setup._ensure_stdin_input()
        raw = f"\x1b[200~{text}\x1b[201~"
        self._setup._stdin_bridge.emit("data", raw)


# ---------------------------------------------------------------------------
# MockMouse
# ---------------------------------------------------------------------------


class MockMouse:
    """Simulate mouse input for tests."""

    def __init__(self, setup: TestSetup) -> None:
        self._setup = setup
        self._x: int = 0
        self._y: int = 0
        self._pressed_buttons: set[int] = set()

    # -- properties ----------------------------------------------------------

    @property
    def position(self) -> tuple[int, int]:
        return self._x, self._y

    @property
    def pressed_buttons(self) -> set[int]:
        return set(self._pressed_buttons)

    # -- dispatch helpers ----------------------------------------------------

    def _dispatch_mouse(self, event: MouseEvent) -> None:
        """Dispatch *event* through the renderer's mouse dispatch.

        Routes through ``CliRenderer._dispatch_mouse_event`` so that hover
        tracking (over/out) and capture logic work the same as production.
        """
        self._setup.renderer._dispatch_mouse_event(event)

    def _dispatch_to_tree(
        self, renderable: Any, event: MouseEvent, scroll_adjust_x: int = 0, scroll_adjust_y: int = 0
    ) -> None:
        """Walk children in reverse order (front-most first), depth-first.

        Accumulates scroll offsets from ancestor ScrollBoxes so that
        ``contains_point`` checks use content-space coordinates.
        """
        if event.propagation_stopped:
            return

        children = list(renderable.get_children()) if hasattr(renderable, "get_children") else []

        # Accumulate scroll offset for children
        child_sx = scroll_adjust_x
        child_sy = scroll_adjust_y
        if getattr(renderable, "_scroll_y", False):
            fn = getattr(renderable, "_scroll_offset_y_fn", None)
            child_sy += int(fn()) if fn else int(getattr(renderable, "_scroll_offset_y", 0))
        if getattr(renderable, "_scroll_x", False):
            child_sx += int(getattr(renderable, "_scroll_offset_x", 0))

        for child in reversed(children):
            self._dispatch_to_tree(child, event, child_sx, child_sy)
            if event.propagation_stopped:
                return

        handler_map = {
            "down": "_on_mouse_down",
            "up": "_on_mouse_up",
            "move": "_on_mouse_move",
            "drag": "_on_mouse_drag",
            "scroll": "_on_mouse_scroll",
        }
        attr = handler_map.get(event.type)
        if attr:
            handler = getattr(renderable, attr, None)
            if handler is not None:
                handler(event)

    # -- public API ----------------------------------------------------------

    def click(
        self,
        x: int,
        y: int,
        button: int = MouseButton.LEFT,
        *,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
    ) -> None:
        """Dispatch a mouse down + up pair (a click)."""
        self._x, self._y = x, y
        self.press_down(x, y, button, shift=shift, ctrl=ctrl, alt=alt)
        self.release(x, y, button, shift=shift, ctrl=ctrl, alt=alt)

    def move_to(self, x: int, y: int) -> None:
        """Move the mouse to *(x, y)*."""
        event_type = "drag" if self._pressed_buttons else "move"
        self._x, self._y = x, y
        event = MouseEvent(type=event_type, x=x, y=y, is_dragging=bool(self._pressed_buttons))
        self._dispatch_mouse(event)

    def press_down(
        self,
        x: int,
        y: int,
        button: int = MouseButton.LEFT,
        *,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
    ) -> None:
        """Press a mouse button down at *(x, y)*."""
        self._x, self._y = x, y
        self._pressed_buttons.add(button)
        event = MouseEvent(type="down", x=x, y=y, button=button, shift=shift, ctrl=ctrl, alt=alt)
        self._dispatch_mouse(event)

    def release(
        self,
        x: int,
        y: int,
        button: int = MouseButton.LEFT,
        *,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
    ) -> None:
        """Release a mouse button at *(x, y)*."""
        self._x, self._y = x, y
        self._pressed_buttons.discard(button)
        event = MouseEvent(type="up", x=x, y=y, button=button, shift=shift, ctrl=ctrl, alt=alt)
        self._dispatch_mouse(event)

    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        steps: int = 5,
        button: int = MouseButton.LEFT,
    ) -> None:
        """Press at *start*, move in *steps* increments, release at *end*."""
        self.press_down(start_x, start_y, button)
        for i in range(1, steps + 1):
            frac = i / steps
            ix = int(start_x + (end_x - start_x) * frac)
            iy = int(start_y + (end_y - start_y) * frac)
            self.move_to(ix, iy)
        self.release(end_x, end_y, button)

    def scroll(
        self,
        x: int,
        y: int,
        direction: str = "down",
        delta: int = 1,
    ) -> None:
        """Dispatch a scroll event at *(x, y)*."""
        scroll_delta = delta if direction == "down" else -delta
        button = MouseButton.WHEEL_DOWN if direction == "down" else MouseButton.WHEEL_UP
        self._x, self._y = x, y
        event = MouseEvent(
            type="scroll",
            x=x,
            y=y,
            button=button,
            scroll_delta=scroll_delta,
            scroll_direction=direction,
        )
        self._dispatch_mouse(event)


# ---------------------------------------------------------------------------
# KeyCodes — terminal escape codes for common keys
# ---------------------------------------------------------------------------


class KeyCodes:
    """Terminal escape codes for common keys."""

    # Control keys
    RETURN = "\r"
    LINEFEED = "\n"
    TAB = "\t"
    BACKSPACE = "\b"
    DELETE = "\x1b[3~"
    HOME = "\x1b[H"
    END = "\x1b[F"
    ESCAPE = "\x1b"

    # Arrow keys
    ARROW_UP = "\x1b[A"
    ARROW_DOWN = "\x1b[B"
    ARROW_RIGHT = "\x1b[C"
    ARROW_LEFT = "\x1b[D"

    # Function keys
    F1 = "\x1bOP"
    F2 = "\x1bOQ"
    F3 = "\x1bOR"
    F4 = "\x1bOS"
    F5 = "\x1b[15~"
    F6 = "\x1b[17~"
    F7 = "\x1b[18~"
    F8 = "\x1b[19~"
    F9 = "\x1b[20~"
    F10 = "\x1b[21~"
    F11 = "\x1b[23~"
    F12 = "\x1b[24~"


# Mapping from KeyCodes attribute names to their values (for resolving key names)
_KEY_CODES_MAP: dict[str, str] = {
    name: getattr(KeyCodes, name) for name in dir(KeyCodes) if not name.startswith("_")
}


# ---------------------------------------------------------------------------
# Kitty keyboard protocol key mappings
# ---------------------------------------------------------------------------

_KITTY_KEY_CODE_MAP: dict[str, int] = {
    "escape": 27,
    "tab": 9,
    "return": 13,
    "backspace": 127,
    "insert": 57348,
    "delete": 57349,
    "left": 57350,
    "right": 57351,
    "up": 57352,
    "down": 57353,
    "pageup": 57354,
    "pagedown": 57355,
    "home": 57356,
    "end": 57357,
    "f1": 57364,
    "f2": 57365,
    "f3": 57366,
    "f4": 57367,
    "f5": 57368,
    "f6": 57369,
    "f7": 57370,
    "f8": 57371,
    "f9": 57372,
    "f10": 57373,
    "f11": 57374,
    "f12": 57375,
}


def _encode_kitty_sequence(
    codepoint: int,
    *,
    shift: bool = False,
    ctrl: bool = False,
    meta: bool = False,
    super_mod: bool = False,
    hyper: bool = False,
) -> str:
    """Encode a key as a kitty keyboard protocol CSI-u sequence."""
    mod_mask = 0
    if shift:
        mod_mask |= 1
    if meta:
        mod_mask |= 2
    if ctrl:
        mod_mask |= 4
    if super_mod:
        mod_mask |= 8
    if hyper:
        mod_mask |= 16

    if mod_mask == 0:
        return f"\x1b[{codepoint}u"
    else:
        return f"\x1b[{codepoint};{mod_mask + 1}u"


def _encode_modify_other_keys_sequence(
    char_code: int,
    *,
    shift: bool = False,
    ctrl: bool = False,
    meta: bool = False,
    super_mod: bool = False,
    hyper: bool = False,
) -> str:
    """Encode a key as a modifyOtherKeys CSI 27;modifier;code~ sequence."""
    mod_mask = 0
    if shift:
        mod_mask |= 1
    if meta:
        mod_mask |= 2
    if ctrl:
        mod_mask |= 4
    if super_mod:
        mod_mask |= 8
    if hyper:
        mod_mask |= 16

    if mod_mask == 0:
        return chr(char_code)

    return f"\x1b[27;{mod_mask + 1};{char_code}~"


def _resolve_key_input(key: str) -> tuple[str, str | None]:
    """Resolve a key input to (key_value, key_name).

    Returns:
        Tuple of (escape-sequence / raw char, optional key name).
    """
    if key in _KEY_CODES_MAP:
        return _KEY_CODES_MAP[key], key.lower()
    return key, None


# ---------------------------------------------------------------------------
# MockRenderer — stdin-level mock for create_mock_keys
# ---------------------------------------------------------------------------


class MockRenderer:
    """A mock renderer that collects raw stdin writes.

    Used by :func:`create_mock_keys` for testing raw escape-sequence
    generation.
    """

    class _Stdin:
        """stdin-like interface used by create_mock_keys."""

        def __init__(self, owner: MockRenderer) -> None:
            self._owner = owner
            self._listeners: list[Any] = []

        def emit(self, event: str, data: str) -> None:
            if event == "data":
                self._owner.emitted_data.append(data)
                for listener in self._listeners:
                    listener(data)

        def on(self, event: str, listener: Any) -> None:
            if event == "data":
                self._listeners.append(listener)

        def write(self, data: str) -> None:
            self.emit("data", data)

    def __init__(self) -> None:
        self.emitted_data: list[str] = []
        self.stdin = MockRenderer._Stdin(self)

    def get_emitted_data(self) -> str:
        return "".join(self.emitted_data)


# ---------------------------------------------------------------------------
# create_mock_keys — simulate raw terminal key sequences for tests
# ---------------------------------------------------------------------------


class MockKeys:
    """Return type of :func:`create_mock_keys`.

    Provides methods for simulating raw terminal key sequences against
    a ``MockRenderer``'s stdin stream.
    """

    def __init__(
        self, renderer: Any, *, kitty_keyboard: bool = False, other_modifiers_mode: bool = False
    ) -> None:
        self._renderer = renderer
        self._kitty = kitty_keyboard
        self._other_mod = other_modifiers_mode and not kitty_keyboard

    # -- internal helpers ---------------------------------------------------

    _VALUE_TO_KEY_NAME: dict[str, str] = {
        "\b": "backspace",
        "\r": "return",
        "\n": "return",
        "\t": "tab",
        "\x1b": "escape",
        "\x1b[A": "up",
        "\x1b[B": "down",
        "\x1b[C": "right",
        "\x1b[D": "left",
        "\x1b[H": "home",
        "\x1b[F": "end",
        "\x1b[3~": "delete",
    }

    _VALUE_TO_CHAR_CODE: dict[str, int] = {
        "\b": 127,
        "\r": 13,
        "\n": 13,
        "\t": 9,
        "\x1b": 27,
        " ": 32,
    }

    _SPECIAL_CTRL_MAP: dict[str, str] = {
        "[": "\x1b",  # ESC (27)
        "\\": "\x1c",  # FS  (28)
        "]": "\x1d",  # GS  (29)
        "^": "\x1e",  # RS  (30)
        "_": "\x1f",  # US  (31)
        "?": "\x7f",  # DEL (127)
        "/": "\x1f",  # same as Ctrl+_
        "-": "\x1f",  # same as Ctrl+_
        ".": "\x1e",  # same as Ctrl+^
        ",": "\x1c",  # same as Ctrl+\
        "@": "\x00",  # NUL (0)
        " ": "\x00",  # NUL (0)
    }

    def _emit(self, data: str) -> None:
        self._renderer.stdin.emit("data", data)

    # -- public API ---------------------------------------------------------

    def press_keys(self, keys: list[str], delay_ms: float = 0) -> None:
        """Press multiple keys in sequence.

        When *delay_ms* > 0 an ``asyncio.sleep`` is inserted between each
        key; callers should ``await`` the result in that case.

        For the synchronous test path the delay is implemented with
        :func:`time.sleep` so that the test's timestamp assertions work.
        """
        import time

        for i, key in enumerate(keys):
            key_value, _ = _resolve_key_input(key)
            self._emit(key_value)
            if delay_ms > 0 and i < len(keys) - 1:
                time.sleep(delay_ms / 1000.0)

    def press_key(
        self,
        key: str,
        modifiers: dict[str, bool] | None = None,
    ) -> None:
        """Press a single key, optionally with modifier flags."""
        shift = (modifiers or {}).get("shift", False)
        ctrl = (modifiers or {}).get("ctrl", False)
        meta = (modifiers or {}).get("meta", False)
        super_mod = (modifiers or {}).get("super", False)
        hyper = (modifiers or {}).get("hyper", False)

        # --- Kitty keyboard protocol mode ---
        if self._kitty:
            key_value, key_name = _resolve_key_input(key)

            if key_value in self._VALUE_TO_KEY_NAME:
                key_name = self._VALUE_TO_KEY_NAME[key_value]
            if key_name and key_name.startswith("arrow_"):
                key_name = key_name[6:]

            if key_name and key_name in _KITTY_KEY_CODE_MAP:
                code = _KITTY_KEY_CODE_MAP[key_name]
                seq = _encode_kitty_sequence(
                    code,
                    shift=shift,
                    ctrl=ctrl,
                    meta=meta,
                    super_mod=super_mod,
                    hyper=hyper,
                )
                self._emit(seq)
                return

            if key_value and len(key_value) == 1 and not key_value.startswith("\x1b"):
                cp = ord(key_value)
                if cp:
                    seq = _encode_kitty_sequence(
                        cp,
                        shift=shift,
                        ctrl=ctrl,
                        meta=meta,
                        super_mod=super_mod,
                        hyper=hyper,
                    )
                    self._emit(seq)
                    return

            # Fall through to regular mode for unknown keys

        # --- modifyOtherKeys mode ---
        if self._other_mod and modifiers:
            key_value, key_name = _resolve_key_input(key)

            char_code: int | None = None
            if key_value in self._VALUE_TO_CHAR_CODE:
                char_code = self._VALUE_TO_CHAR_CODE[key_value]
            elif key_value and len(key_value) == 1 and not key_value.startswith("\x1b"):
                char_code = ord(key_value)

            if char_code is not None:
                seq = _encode_modify_other_keys_sequence(
                    char_code,
                    shift=shift,
                    ctrl=ctrl,
                    meta=meta,
                    super_mod=super_mod,
                    hyper=hyper,
                )
                self._emit(seq)
                return

            # Fall through to regular mode for arrow keys etc.

        # --- Regular mode ---
        key_code, _ = _resolve_key_input(key)

        if modifiers:
            import re as _re

            if key_code.startswith("\x1b[") and len(key_code) > 2:
                modifier_val = (
                    1
                    + (1 if shift else 0)
                    + (2 if meta else 0)
                    + (4 if ctrl else 0)
                    + (8 if super_mod else 0)
                    + (16 if hyper else 0)
                )
                if modifier_val > 1:
                    tilde_match = _re.match(r"^\x1b\[(\d+)~$", key_code)
                    if tilde_match:
                        key_code = f"\x1b[{tilde_match.group(1)};{modifier_val}~"
                    else:
                        ending = key_code[-1]
                        key_code = f"\x1b[1;{modifier_val}{ending}"
            elif len(key_code) == 1:
                char = key_code

                if char == "\b" and (ctrl or super_mod or hyper):
                    modifier_val = (
                        1
                        + (1 if shift else 0)
                        + (2 if meta else 0)
                        + (4 if ctrl else 0)
                        + (8 if super_mod else 0)
                        + (16 if hyper else 0)
                    )
                    key_code = f"\x1b[27;{modifier_val};127~"
                elif ctrl:
                    if "a" <= char <= "z":
                        key_code = chr(ord(char) - 96)
                    elif "A" <= char <= "Z":
                        key_code = chr(ord(char) - 64)
                    elif char in self._SPECIAL_CTRL_MAP:
                        key_code = self._SPECIAL_CTRL_MAP[char]
                    # else: keep original character

                    if meta:
                        key_code = f"\x1b{key_code}"
                else:
                    if shift and "a" <= char <= "z":
                        char = char.upper()
                    key_code = f"\x1b{char}" if meta else char
            elif meta and not key_code.startswith("\x1b"):
                key_code = f"\x1b{key_code}"

        self._emit(key_code)

    def type_text(self, text: str, delay_ms: float = 0) -> None:
        """Type text — one key event per character."""
        self.press_keys(list(text), delay_ms)

    def press_enter(self, modifiers: dict[str, bool] | None = None) -> None:
        self.press_key(KeyCodes.RETURN, modifiers)

    def press_escape(self, modifiers: dict[str, bool] | None = None) -> None:
        self.press_key(KeyCodes.ESCAPE, modifiers)

    def press_tab(self, modifiers: dict[str, bool] | None = None) -> None:
        self.press_key(KeyCodes.TAB, modifiers)

    def press_backspace(self, modifiers: dict[str, bool] | None = None) -> None:
        self.press_key(KeyCodes.BACKSPACE, modifiers)

    def press_arrow(
        self,
        direction: str,
        modifiers: dict[str, bool] | None = None,
    ) -> None:
        key_map = {
            "up": KeyCodes.ARROW_UP,
            "down": KeyCodes.ARROW_DOWN,
            "left": KeyCodes.ARROW_LEFT,
            "right": KeyCodes.ARROW_RIGHT,
        }
        self.press_key(key_map[direction], modifiers)

    def press_ctrl_c(self) -> None:
        self.press_key("c", {"ctrl": True})


def create_mock_keys(
    renderer: Any,
    options: dict[str, bool] | None = None,
) -> MockKeys:
    """Create a MockKeys instance for testing raw escape-sequence generation.

    Args:
        renderer: A ``MockRenderer`` (or any object with a ``.stdin`` that
            has an ``emit("data", ...)`` method).
        options: Dict with optional keys ``kittyKeyboard`` and
            ``otherModifiersMode``.

    Returns:
        A :class:`MockKeys` instance.
    """
    opts = options or {}
    return MockKeys(
        renderer,
        kitty_keyboard=opts.get("kittyKeyboard", False),
        other_modifiers_mode=opts.get("otherModifiersMode", False),
    )


# ---------------------------------------------------------------------------
# SGRMockMouse — generates SGR escape sequences for mouse events
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


import re as _re

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
        x = int(m.group(2)) - 1  # 1-based → 0-based
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


# ---------------------------------------------------------------------------
# TestRecorder — captures frames from the render pipeline
# ---------------------------------------------------------------------------

import ctypes
import time
from dataclasses import dataclass, field


@dataclass
class RecordedBuffers:
    """Buffer data captured from a single frame."""

    fg: list[float] | None = None
    bg: list[float] | None = None
    attributes: list[int] | None = None


@dataclass
class RecordedFrame:
    """A single captured frame from the TestRecorder."""

    frame: str
    timestamp: float
    frame_number: int
    buffers: RecordedBuffers | None = None


class TestRecorder:
    """Records frames from a renderer by hooking into the render pipeline."""

    __test__ = False  # Not a pytest test class

    def __init__(self, renderer: Any, options: dict | None = None) -> None:
        self._renderer = renderer
        self._frames: list[RecordedFrame] = []
        self._recording = False
        self._frame_number = 0
        self._start_time: float = 0
        self._original_render_frame: Any = None
        opts = options or {}
        self._record_buffers: dict = opts.get("record_buffers", {})
        self._now: Callable[[], float] = opts.get("now", lambda: time.monotonic() * 1000)

    def rec(self) -> None:
        """Start recording frames."""
        if self._recording:
            return

        self._recording = True
        self._frames = []
        self._frame_number = 0
        self._start_time = self._now()

        original = self._renderer._render_frame
        self._original_render_frame = original

        def hooked_render_frame(dt: float) -> None:
            original(dt)
            if self._recording:
                self._capture_frame()

        self._renderer._render_frame = hooked_render_frame

    def stop(self) -> None:
        """Stop recording and restore original render method."""
        if not self._recording:
            return

        self._recording = False

        if self._original_render_frame is not None:
            self._renderer._render_frame = self._original_render_frame
            self._original_render_frame = None

    @property
    def recorded_frames(self) -> list[RecordedFrame]:
        """Return a copy of the recorded frames list."""
        return list(self._frames)

    @property
    def is_recording(self) -> bool:
        return self._recording

    def clear(self) -> None:
        """Clear all recorded frames."""
        self._frames = []
        self._frame_number = 0

    def _capture_frame(self) -> None:
        """Capture the current frame from the renderer's buffer."""
        buffer = self._renderer.get_current_buffer()
        frame_text = buffer.get_plain_text()

        recorded = RecordedFrame(
            frame=frame_text,
            timestamp=self._now() - self._start_time,
            frame_number=self._frame_number,
        )
        self._frame_number += 1

        if (
            self._record_buffers.get("fg")
            or self._record_buffers.get("bg")
            or self._record_buffers.get("attributes")
        ):
            w = buffer.width
            h = buffer.height
            size = w * h
            buffers = RecordedBuffers()

            if self._record_buffers.get("fg"):
                fg_ptr = buffer._native.buffer_get_fg_ptr(buffer._ptr)
                arr = (ctypes.c_float * (size * 4)).from_address(fg_ptr)
                buffers.fg = list(arr)

            if self._record_buffers.get("bg"):
                bg_ptr = buffer._native.buffer_get_bg_ptr(buffer._ptr)
                arr = (ctypes.c_float * (size * 4)).from_address(bg_ptr)
                buffers.bg = list(arr)

            if self._record_buffers.get("attributes"):
                attr_ptr = buffer._native.buffer_get_attributes_ptr(buffer._ptr)
                arr = (ctypes.c_uint32 * size).from_address(attr_ptr)
                buffers.attributes = list(arr)

            recorded.buffers = buffers

        self._frames.append(recorded)


# ---------------------------------------------------------------------------
# capture_spans — reads buffer and groups cells into styled spans
# ---------------------------------------------------------------------------


@dataclass
class CapturedSpan:
    """A contiguous run of cells with the same styling."""

    text: str
    width: int
    fg: Any  # RGBA
    bg: Any  # RGBA
    attributes: int


@dataclass
class CapturedLine:
    """A single line of captured spans."""

    spans: list[CapturedSpan] = field(default_factory=list)


@dataclass
class CapturedFrame:
    """Full frame capture with styled spans."""

    cols: int
    rows: int
    lines: list[CapturedLine]
    cursor: tuple[int, int]


def capture_spans(renderer: Any) -> CapturedFrame:
    """Read the current buffer and group cells into styled spans.

    Iterates over every cell in the buffer, reading fg color, bg color,
    attributes, and character. Adjacent cells with matching style are
    grouped into a single :class:`CapturedSpan`.

    Args:
        renderer: A CliRenderer instance.

    Returns:
        A :class:`CapturedFrame` with cols, rows, lines (list of CapturedLine),
        and cursor position.
    """
    from . import structs as s

    buffer = renderer.get_current_buffer()
    w = buffer.width
    h = buffer.height

    # Get raw text for character data
    try:
        raw: bytes = buffer._native.buffer_write_resolved_chars(buffer._ptr, True)
        text = raw.decode("utf-8", errors="replace") if raw else ""
    except Exception:
        text = ""

    text_lines = text.split("\n")

    # Get buffer pointers
    fg_ptr = buffer._native.buffer_get_fg_ptr(buffer._ptr)
    bg_ptr = buffer._native.buffer_get_bg_ptr(buffer._ptr)
    attr_ptr = buffer._native.buffer_get_attributes_ptr(buffer._ptr)

    lines: list[CapturedLine] = []

    for y in range(h):
        line_text = text_lines[y] if y < len(text_lines) else ""
        spans: list[CapturedSpan] = []
        current_text = ""
        current_width = 0
        current_fg: s.RGBA | None = None
        current_bg: s.RGBA | None = None
        current_attr: int | None = None

        for x in range(w):
            # Read fg color
            fg_offset = (y * w + x) * 4
            fg_arr = (ctypes.c_float * 4).from_address(
                fg_ptr + fg_offset * ctypes.sizeof(ctypes.c_float)
            )
            fg = s.RGBA(fg_arr[0], fg_arr[1], fg_arr[2], fg_arr[3])

            # Read bg color
            bg_arr = (ctypes.c_float * 4).from_address(
                bg_ptr + fg_offset * ctypes.sizeof(ctypes.c_float)
            )
            bg = s.RGBA(bg_arr[0], bg_arr[1], bg_arr[2], bg_arr[3])

            # Read attributes
            attr_offset = y * w + x
            a_arr = (ctypes.c_uint32 * 1).from_address(
                attr_ptr + attr_offset * ctypes.sizeof(ctypes.c_uint32)
            )
            attr = a_arr[0]

            # Get character from resolved text
            ch = line_text[x] if x < len(line_text) else " "

            # Check if this cell continues the current span
            if (
                current_fg is not None
                and fg == current_fg
                and bg == current_bg
                and attr == current_attr
            ):
                current_text += ch
                current_width += 1
            else:
                # Flush current span
                if current_fg is not None:
                    spans.append(
                        CapturedSpan(
                            text=current_text,
                            width=current_width,
                            fg=current_fg,
                            bg=current_bg,
                            attributes=current_attr,  # type: ignore[arg-type]
                        )
                    )
                current_text = ch
                current_width = 1
                current_fg = fg
                current_bg = bg
                current_attr = attr

        # Flush last span
        if current_fg is not None:
            spans.append(
                CapturedSpan(
                    text=current_text,
                    width=current_width,
                    fg=current_fg,
                    bg=current_bg,
                    attributes=current_attr,  # type: ignore[arg-type]
                )
            )

        lines.append(CapturedLine(spans=spans))

    # Get cursor position
    cursor_x = getattr(renderer, "_cursor_x", 0)
    cursor_y = getattr(renderer, "_cursor_y", 0)

    return CapturedFrame(cols=w, rows=h, lines=lines, cursor=(cursor_x, cursor_y))


__all__ = [
    "BufferDiff",
    "DiffResult",
    "assert_buffer_equal",
    "MockInput",
    "MockMouse",
    "SGRMockMouse",
    "SGRMockRenderer",
    "SGRMouseButtons",
    "create_mock_mouse",
    "SGRMouseParser",
    "KeyCodes",
    "MockRenderer",
    "MockKeys",
    "create_mock_keys",
    "_TestStdinBridge",
    "TestRecorder",
    "RecordedFrame",
    "RecordedBuffers",
    "CapturedSpan",
    "CapturedLine",
    "CapturedFrame",
    "capture_spans",
]
