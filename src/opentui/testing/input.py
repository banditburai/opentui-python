"""Testing utilities — keyboard/mouse mocks and terminal escape-sequence helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import hooks
from ..events import KeyEvent, Keys, MouseButton, MouseEvent

if TYPE_CHECKING:
    from . import TestSetup


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
        from ..attachments import normalize_paste_payload

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
# MockKeys — simulate raw terminal key sequences for tests
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
    """Args:
    renderer: A ``MockRenderer`` (or any object with a ``.stdin`` that
        has an ``emit("data", ...)`` method).
    options: Dict with optional keys ``kittyKeyboard`` and
        ``otherModifiersMode``.
    """
    opts = options or {}
    return MockKeys(
        renderer,
        kitty_keyboard=opts.get("kittyKeyboard", False),
        other_modifiers_mode=opts.get("otherModifiersMode", False),
    )
