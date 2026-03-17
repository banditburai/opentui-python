"""Event types for OpenTUI Python."""

from __future__ import annotations

from dataclasses import dataclass, field


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
class KeyEvent:
    """Keyboard event.

    Attributes:
        key: Key name (e.g., "return", "escape", "a", "space")
        code: Key code (e.g., "KeyA", "Enter", "Escape")
        ctrl: Whether Ctrl key is pressed
        shift: Whether Shift key is pressed
        alt: Whether Alt key is pressed
        meta: Whether Meta (Cmd/Windows) key is pressed
        hyper: Whether Hyper modifier is pressed (kitty bit 4)
        caps_lock: Whether CapsLock is active (kitty bit 6)
        num_lock: Whether NumLock is active (kitty bit 7)
        repeated: Whether the key is being held down (auto-repeat)
        event_type: "press" or "release"
        sequence: Associated text from the key event (kitty CSI-u field 3
            or raw character). Used for text insertion — may differ from
            ``key`` when IME composition is active.
        source: Parser source — ``"raw"`` for legacy or ``"kitty"`` for
            kitty keyboard protocol.
        number: Whether the key is a digit (0-9).
    """

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

    def stop_propagation(self) -> None:
        """Stop event from propagating to parent handlers."""
        self._propagation_stopped = True

    def prevent_default(self) -> None:
        """Prevent default action for this event."""
        self._default_prevented = True

    @property
    def propagation_stopped(self) -> bool:
        return self._propagation_stopped

    @property
    def default_prevented(self) -> bool:
        return self._default_prevented

    @property
    def name(self) -> str:
        """Alias for key."""
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
class MouseEvent:
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

    def stop_propagation(self) -> None:
        """Stop event from propagating to parent handlers."""
        self._propagation_stopped = True

    def prevent_default(self) -> None:
        """Prevent default action for this event."""
        self._default_prevented = True

    @property
    def propagation_stopped(self) -> bool:
        return self._propagation_stopped

    @property
    def default_prevented(self) -> bool:
        return self._default_prevented

    @property
    def name(self) -> str:
        """Alias for type."""
        return self.type

    def __str__(self) -> str:
        return f"MouseEvent({self.type} at {self.x},{self.y})"


@dataclass
class PasteEvent:
    """Paste event.

    Attributes:
        text: The pasted text
        attachments: Structured attachments from a paste/drop payload
    """

    text: str | None = None
    attachments: list[AttachmentPayload] = field(default_factory=list)
    _propagation_stopped: bool = field(default=False, repr=False)
    _default_prevented: bool = field(default=False, repr=False)

    def stop_propagation(self) -> None:
        """Stop event from propagating to parent handlers."""
        self._propagation_stopped = True

    def prevent_default(self) -> None:
        """Prevent default action for this event."""
        self._default_prevented = True

    @property
    def propagation_stopped(self) -> bool:
        return self._propagation_stopped

    @property
    def default_prevented(self) -> bool:
        return self._default_prevented

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


__all__ = [
    "AttachmentPayload",
    "KeyEvent",
    "MouseEvent",
    "PasteEvent",
    "FocusEvent",
    "ResizeEvent",
    "Keys",
    "MouseButton",
]
