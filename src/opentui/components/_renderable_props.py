"""Renderable property descriptors and dirty-level plumbing."""

from __future__ import annotations

from collections.abc import Callable

_DIRTY_NONE = 0
_DIRTY_LAYOUT = 1
_DIRTY_PAINT = 2
_DIRTY_HIT_PAINT = 3

_MOUSE_TRACKING_CACHE_SLOTS = frozenset(
    {
        "_visible",
        "_on_mouse_down",
        "_on_mouse_up",
        "_on_mouse_move",
        "_on_mouse_drag",
        "_on_mouse_drag_end",
        "_on_mouse_drop",
        "_on_mouse_over",
        "_on_mouse_out",
        "_on_mouse_scroll",
    }
)


class _Prop:
    """Descriptor for slot access with optional transform and dirty marking."""

    __slots__ = ("_slot", "_transform", "_dirty")

    def __init__(
        self,
        slot: str,
        transform: Callable | None = None,
        *,
        paint_only: bool = False,
        hit_paint: bool = False,
        dirty: bool = True,
    ):
        self._slot = slot
        self._transform = transform
        if not dirty:
            self._dirty = _DIRTY_NONE
        elif hit_paint:
            self._dirty = _DIRTY_HIT_PAINT
        elif paint_only:
            self._dirty = _DIRTY_PAINT
        else:
            self._dirty = _DIRTY_LAYOUT

    def __get__(self, obj, objtype=None):
        return getattr(obj, self._slot) if obj is not None else self

    def __set__(self, obj, value):
        if self._transform is not None:
            value = self._transform(value)
        setattr(obj, self._slot, value)
        if self._slot in _MOUSE_TRACKING_CACHE_SLOTS:
            obj._invalidate_mouse_tracking_cache()
        d = self._dirty
        if d == _DIRTY_LAYOUT:
            obj.mark_dirty()
        elif d == _DIRTY_HIT_PAINT:
            obj.mark_hit_paint_dirty()
        elif d == _DIRTY_PAINT:
            obj.mark_paint_dirty()


__all__ = ["_Prop"]
