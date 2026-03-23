"""Behavior mixin for Renderable interaction and live-state helpers."""

from __future__ import annotations

from typing import Any

from ._renderable_base import BaseRenderable


class _RenderableBehaviorMixin:
    @property
    def display(self) -> str:
        return "flex" if self._visible else "none"

    @display.setter
    def display(self, value: str) -> None:
        self.visible = value != "none"

    @BaseRenderable.visible.setter
    def visible(self, value: bool) -> None:
        old = self._visible
        if old == value:
            return
        self._visible = value
        self._invalidate_mouse_tracking_cache()
        self._sync_yoga_display()
        self.mark_dirty()
        if self._live:
            self._propagate_live_count(1 if value else -1)

    @property
    def live(self) -> bool:
        return self._live

    @live.setter
    def live(self, value: bool) -> None:
        if self._live == value:
            return
        self._live = value
        if self._visible:
            self._propagate_live_count(1 if value else -1)

    @property
    def live_count(self) -> int:
        return self._live_count

    def _propagate_live_count(self, delta: int) -> None:
        self._live_count += delta
        parent = self._parent
        if parent is not None and hasattr(parent, "_propagate_live_count"):
            parent._propagate_live_count(delta)

    def focus(self) -> None:
        self.focused = True

    def blur(self) -> None:
        self.focused = False

    def handle_key_press(self, key: Any) -> bool:
        return False

    def should_start_selection(self, x: int, y: int) -> bool:
        return False

    def has_selection(self) -> bool:
        return False

    def on_selection_changed(self, selection: Any) -> bool:
        return False

    def get_selected_text(self) -> str:
        return ""

    def dispatch_paste(self, event: Any) -> None:
        if self._on_paste is not None:
            self._on_paste(event)
        if self._destroyed:
            return
        prevented = getattr(event, "default_prevented", False)
        if not prevented and self._handle_paste is not None:
            self._handle_paste(event)


__all__ = ["_RenderableBehaviorMixin"]
