"""Event types for OpenTUI Python."""

from dataclasses import dataclass


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
        repeated: Whether the key is being held down (auto-repeat)
    """

    key: str
    code: str = ""
    ctrl: bool = False
    shift: bool = False
    alt: bool = False
    meta: bool = False
    repeated: bool = False

    @property
    def name(self) -> str:
        """Alias for key - matches JS API."""
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
    """

    type: str
    x: int
    y: int
    button: int = 0
    scroll_delta: int = 0
    shift: bool = False
    ctrl: bool = False
    alt: bool = False

    @property
    def name(self) -> str:
        """Alias for type - matches JS API."""
        return self.type

    def __str__(self) -> str:
        return f"MouseEvent({self.type} at {self.x},{self.y})"


@dataclass
class PasteEvent:
    """Paste event.

    Attributes:
        text: The pasted text
    """

    text: str

    def __str__(self) -> str:
        return f"PasteEvent({self.text[:20]!r}...)"


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


__all__ = [
    "KeyEvent",
    "MouseEvent",
    "PasteEvent",
    "FocusEvent",
    "ResizeEvent",
    "Keys",
]
