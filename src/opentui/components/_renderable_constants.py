"""Shared internal constants for renderable internals."""

import sys as _sys

# Pointer identity with C++-interned strings enables O(1) comparison in yoga.
_COLUMN = _sys.intern("column")
_NOWRAP = _sys.intern("nowrap")
_FLEX_START = _sys.intern("flex-start")
_STRETCH = _sys.intern("stretch")
_VISIBLE = _sys.intern("visible")
_RELATIVE = _sys.intern("relative")
_SINGLE = _sys.intern("single")
_LEFT = _sys.intern("left")

_SIMPLE_DEFAULTS: dict[str, object] = {
    "_min_width": None,
    "_min_height": None,
    "_max_width": None,
    "_max_height": None,
    "_flex_grow": 0,
    "_flex_shrink": 1,
    "_flex_direction": _COLUMN,
    "_flex_wrap": _NOWRAP,
    "_flex_basis": None,
    "_justify_content": _FLEX_START,
    "_align_items": _STRETCH,
    "_align_self": None,
    "_gap": 0,
    "_row_gap": None,
    "_column_gap": None,
    "_overflow": _VISIBLE,
    "_position": _RELATIVE,
    "_padding": 0,
    "_padding_top": 0,
    "_padding_right": 0,
    "_padding_bottom": 0,
    "_padding_left": 0,
    "_margin": 0,
    "_margin_top": 0,
    "_margin_right": 0,
    "_margin_bottom": 0,
    "_margin_left": 0,
    "_background_color": None,
    "_fg": None,
    "_border": False,
    "_border_style": _SINGLE,
    "_border_color": None,
    "_title": None,
    "_title_alignment": _LEFT,
    "_border_top": True,
    "_border_right": True,
    "_border_bottom": True,
    "_border_left": True,
    "_border_chars": None,
    "_focusable": False,
    "_focused": False,
    "_focused_border_color": None,
    "_opacity": 1.0,
    "_z_index": 0,
    "_pos_top": None,
    "_pos_right": None,
    "_pos_bottom": None,
    "_pos_left": None,
    "_translate_x": 0,
    "_translate_y": 0,
    "_render_before": None,
    "_render_after": None,
    "_on_size_change": None,
    "_on_lifecycle_pass": None,
    "_on_mouse_down": None,
    "_on_mouse_up": None,
    "_on_mouse_move": None,
    "_on_mouse_drag": None,
    "_on_mouse_drag_end": None,
    "_on_mouse_drop": None,
    "_on_mouse_over": None,
    "_on_mouse_out": None,
    "_on_mouse_scroll": None,
    "_on_key_down": None,
    "_on_paste": None,
    "_live": False,
    "_live_count": 0,
    "_handle_paste": None,
    "_selectable": False,
    "_children_tuple": None,
    "_width": None,
    "_height": None,
    "_visible": True,
}

_UNSET_FLEX_SHRINK = object()

__all__ = [
    "_COLUMN",
    "_FLEX_START",
    "_LEFT",
    "_NOWRAP",
    "_RELATIVE",
    "_SIMPLE_DEFAULTS",
    "_SINGLE",
    "_STRETCH",
    "_UNSET_FLEX_SHRINK",
    "_VISIBLE",
]
