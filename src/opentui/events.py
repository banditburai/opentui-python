"""Event types for OpenTUI Python."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class _EventPropagationMixin:
    """Shared event propagation behavior for KeyEvent, MouseEvent, PasteEvent."""

    def stop_propagation(self) -> None:
        """Stop event from propagating to parent handlers."""
        self._propagation_stopped = True

    stop = stop_propagation

    def prevent_default(self) -> None:
        """Prevent default action for this event."""
        self._default_prevented = True

    prevent = prevent_default

    @property
    def propagation_stopped(self) -> bool:
        return self._propagation_stopped

    @property
    def default_prevented(self) -> bool:
        return self._default_prevented


class MouseButton:
    """Mouse button constants."""

    LEFT = 0
    MIDDLE = 1
    RIGHT = 2
    WHEEL_UP = 4
    WHEEL_DOWN = 5
    WHEEL_LEFT = 6
    WHEEL_RIGHT = 7


@dataclass
class AttachmentPayload:
    """Attachment payload carried by paste/drop events."""

    kind: str
    name: str | None = None
    mime_type: str | None = None
    path: str | None = None
    data: bytes | None = None
    text: str | None = None


@dataclass
class KeyEvent(_EventPropagationMixin):
    key: str
    code: str = ""
    ctrl: bool = False
    shift: bool = False
    alt: bool = False
    meta: bool = False
    hyper: bool = False
    caps_lock: bool = False
    num_lock: bool = False
    repeated: bool = False
    event_type: str = "press"
    sequence: str = ""
    source: str = "raw"
    number: bool = False
    base_code: int = 0
    _propagation_stopped: bool = field(default=False, repr=False)
    _default_prevented: bool = field(default=False, repr=False)

    @property
    def name(self) -> str:
        return self.key

    def __str__(self) -> str:
        parts = []
        if self.ctrl:
            parts.append("ctrl")
        if self.alt:
            parts.append("alt")
        if self.shift:
            parts.append("shift")
        if self.meta:
            parts.append("meta")
        if self.hyper:
            parts.append("hyper")
        parts.append(self.key)
        return "+".join(parts)


@dataclass
class MouseEvent(_EventPropagationMixin):
    """Mouse event.

    Attributes:
        type: Event type ("down", "up", "move", "scroll", "drag", "over", "out")
        x: X position in terminal cells
        y: Y position in terminal cells
        button: Mouse button (0=left, 1=middle, 2=right)
        scroll_delta: Scroll amount (for scroll events)
        shift: Whether Shift key is pressed
        ctrl: Whether Ctrl key is pressed
        alt: Whether Alt key is pressed
        source: The renderable that originally received the event
        target: The renderable that the event is being dispatched to
        is_dragging: Whether a drag operation is in progress
    """

    type: str
    x: int
    y: int
    button: int = 0
    scroll_delta: int = 0
    scroll_direction: str | None = None
    shift: bool = False
    ctrl: bool = False
    alt: bool = False
    source: object = None
    target: object = None
    is_dragging: bool = False
    _propagation_stopped: bool = field(default=False, repr=False)
    _default_prevented: bool = field(default=False, repr=False)

    @property
    def name(self) -> str:
        return self.type

    def __str__(self) -> str:
        return f"MouseEvent({self.type} at {self.x},{self.y})"


@dataclass
class PasteEvent(_EventPropagationMixin):
    """Paste event.

    Attributes:
        text: The pasted text
        attachments: Structured attachments from a paste/drop payload
    """

    text: str | None = None
    attachments: list[AttachmentPayload] = field(default_factory=list)
    _propagation_stopped: bool = field(default=False, repr=False)
    _default_prevented: bool = field(default=False, repr=False)

    def __str__(self) -> str:
        text = self.text or ""
        return f"PasteEvent({text[:20]!r}...)"


@dataclass
class FocusEvent:
    """Focus event.

    Attributes:
        type: Event type ("focus" or "blur")
        target: The renderable that gained/lost focus
    """

    type: str
    target: object

    def __str__(self) -> str:
        return f"FocusEvent({self.type})"


@dataclass
class ResizeEvent:
    """Resize event.

    Attributes:
        width: New width in terminal cells
        height: New height in terminal cells
    """

    width: int
    height: int

    def __str__(self) -> str:
        return f"ResizeEvent({self.width}x{self.height})"


# Common key names
class Keys:
    """Common key names."""

    RETURN = "return"
    ENTER = "return"
    ESCAPE = "escape"
    ESC = "escape"
    BACKSPACE = "backspace"
    DELETE = "delete"
    TAB = "tab"
    SPACE = "space"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    HOME = "home"
    END = "end"
    PAGE_UP = "pageup"
    PAGE_DOWN = "pagedown"
    INSERT = "insert"
    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    F6 = "f6"
    F7 = "f7"
    F8 = "f8"
    F9 = "f9"
    F10 = "f10"
    F11 = "f11"
    F12 = "f12"
    LINEFEED = "linefeed"
    CLEAR = "clear"


def handler(
    callback: Callable[..., Any],
    *args: Any,
    stop: bool = False,
    prevent: bool = False,
    pass_event: bool = False,
) -> Callable[[Any], None]:
    """Create event handler with eagerly captured args.

    Solves stale closures in loops and stop_propagation boilerplate.

    Args:
        callback: The function to call when the event fires.
        *args: Arguments captured eagerly (not lazily) for the callback.
        stop: If True, calls ``event.stop_propagation()`` before the callback.
        prevent: If True, calls ``event.prevent_default()`` before the callback.
        pass_event: If True, the event object is passed as the first argument
            to ``callback`` (before ``*args``).

    Examples::

        handler(do_save)
        handler(select_item, item_id, stop=True)
        handler(handle_click, item_id, stop=True, pass_event=True)
    """

    def _handler(event: Any) -> None:
        if stop:
            event.stop_propagation()
        if prevent:
            event.prevent_default()
        if pass_event:
            callback(event, *args)
        else:
            callback(*args)

    return _handler


def click_handler(
    callback: Callable[..., Any],
    *args: Any,
) -> Callable[[Any], None]:
    """Shorthand for left-click handlers with auto stop_propagation.

    Only fires on left button (button==0). Automatically stops propagation.
    The event object is NOT passed to callback.

    Examples::

        Box(on_mouse_down=click_handler(select_item, item.id))
    """

    def _handler(event: Any) -> None:
        if getattr(event, "button", -1) != 0:
            return
        event.stop_propagation()
        callback(*args)

    return _handler


__all__ = [
    "AttachmentPayload",
    "KeyEvent",
    "MouseEvent",
    "PasteEvent",
    "FocusEvent",
    "ResizeEvent",
    "Keys",
    "MouseButton",
    "click_handler",
    "handler",
]
