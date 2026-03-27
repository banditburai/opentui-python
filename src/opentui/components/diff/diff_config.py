from dataclasses import dataclass
from typing import Any

from ... import structs as s


@dataclass(frozen=True, slots=True)
class DiffRenderConfig:
    diff_text: str
    view_mode: str
    diff_fg: s.RGBA | None
    filetype: str | None
    wrap_mode: str | None
    conceal: bool
    show_line_numbers: bool
    line_number_fg_color: s.RGBA | None
    line_number_bg_color: s.RGBA | None
    added_bg: s.RGBA
    removed_bg: s.RGBA
    context_bg: s.RGBA | None
    added_content_bg: s.RGBA | None
    removed_content_bg: s.RGBA | None
    context_content_bg: s.RGBA | None
    added_sign_color: s.RGBA
    removed_sign_color: s.RGBA
    added_line_number_bg: s.RGBA | None
    removed_line_number_bg: s.RGBA | None


def resolve_diff_render_config(
    parse_color,
    *,
    diff: str,
    view: str,
    fg,
    filetype: str | None,
    wrap_mode: str | None,
    conceal: bool,
    show_line_numbers: bool,
    line_number_fg,
    line_number_bg,
    added_bg,
    removed_bg,
    context_bg,
    added_content_bg,
    removed_content_bg,
    context_content_bg,
    added_sign_color,
    removed_sign_color,
    added_line_number_bg,
    removed_line_number_bg,
) -> DiffRenderConfig:
    return DiffRenderConfig(
        diff_text=diff,
        view_mode=view,
        diff_fg=parse_color(fg) if fg else None,
        filetype=filetype,
        wrap_mode=wrap_mode,
        conceal=conceal,
        show_line_numbers=show_line_numbers,
        line_number_fg_color=parse_color(line_number_fg),
        line_number_bg_color=parse_color(line_number_bg),
        added_bg=parse_color(added_bg) or s.RGBA(0.102, 0.302, 0.102, 1),
        removed_bg=parse_color(removed_bg) or s.RGBA(0.302, 0.102, 0.102, 1),
        context_bg=parse_color(context_bg),
        added_content_bg=parse_color(added_content_bg),
        removed_content_bg=parse_color(removed_content_bg),
        context_content_bg=parse_color(context_content_bg),
        added_sign_color=parse_color(added_sign_color) or s.RGBA(0.133, 0.773, 0.369, 1),
        removed_sign_color=parse_color(removed_sign_color) or s.RGBA(0.937, 0.267, 0.267, 1),
        added_line_number_bg=parse_color(added_line_number_bg),
        removed_line_number_bg=parse_color(removed_line_number_bg),
    )


class DiffCodeAdapter:
    """Adapter providing CodeRenderable-like API for DiffRenderable panes."""

    def __init__(self, owner: Any, side: str):
        self._owner = owner
        self._side = side
        self._event_handlers: dict[str, list] = {}

    @property
    def fg(self) -> s.RGBA | None:
        return self._owner._diff_fg

    @fg.setter
    def fg(self, value: s.RGBA | None) -> None:
        self._owner._diff_fg = value

    @property
    def content(self) -> str:
        if self._side == "left":
            if self._owner._view_mode == "unified":
                return "\n".join(self._owner._unified_lines)
            return "\n".join(self._owner._left_lines)
        return "\n".join(self._owner._right_lines)

    @content.setter
    def content(self, value: str) -> None:  # noqa: ARG002
        # Content is computed from diff — setter exists for CodeRenderable protocol compliance
        self.emit("line-info-change")

    def on(self, event: str, handler: Any) -> None:
        self._event_handlers.setdefault(event, []).append(handler)

    def off(self, event: str, handler: Any | None = None) -> None:
        if event not in self._event_handlers:
            return
        if handler is None:
            self._event_handlers[event] = []
            return
        self._event_handlers[event] = [h for h in self._event_handlers[event] if h != handler]

    def emit(self, event: str, *args: Any) -> None:
        for handler in self._event_handlers.get(event, []):
            handler(*args)

    def listener_count(self, event: str) -> int:
        return len(self._event_handlers.get(event, []))


class DiffLineNumberAdapter:
    """Adapter providing LineNumberRenderable-like API for DiffRenderable panes."""

    def __init__(self, owner: Any, side: str):
        self._owner = owner
        self._side = side

    @property
    def is_destroyed(self) -> bool:
        return self._owner._destroyed


__all__ = [
    "DiffCodeAdapter",
    "DiffLineNumberAdapter",
    "DiffRenderConfig",
    "resolve_diff_render_config",
]
