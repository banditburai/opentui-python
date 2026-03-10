"""Testing utilities for OpenTUI Python — BufferDiff, MockInput, MockMouse."""

from __future__ import annotations

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

        for y, (exp_line, act_line) in enumerate(zip(self.expected, self.actual)):
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
        for handler in hooks.get_paste_handlers():
            handler(text)


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
        """Dispatch *event* through the renderable tree (children first, front-to-back)."""
        root = self._setup.renderer.root
        self._dispatch_to_tree(root, event)

    def _dispatch_to_tree(self, renderable: Any, event: MouseEvent) -> None:
        """Walk children in reverse order (front-most first), depth-first."""
        if event.propagation_stopped:
            return

        children = list(renderable.get_children()) if hasattr(renderable, "get_children") else []
        for child in reversed(children):
            self._dispatch_to_tree(child, event)
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


__all__ = ["BufferDiff", "DiffResult", "assert_buffer_equal", "MockInput", "MockMouse"]
