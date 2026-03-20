"""SelectRenderable - keyboard-navigable option list renderable."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import structs as s
from ..enums import RenderStrategy
from ..events import KeyEvent
from ..keymapping import (
    DEFAULT_KEY_ALIASES,
    KeyAliasMap,
    KeyBinding,
    build_key_bindings_map,
    lookup_action,
    merge_key_aliases,
    merge_key_bindings,
)
from ..native import _nb
from .base import Renderable
from .input import SelectOption

if TYPE_CHECKING:
    from ..renderer import Buffer


_DEFAULT_SELECT_BINDINGS: list[KeyBinding] = [
    KeyBinding(name="up", action="move-up"),
    KeyBinding(name="k", action="move-up"),
    KeyBinding(name="down", action="move-down"),
    KeyBinding(name="j", action="move-down"),
    KeyBinding(name="up", action="move-up-fast", shift=True),
    KeyBinding(name="down", action="move-down-fast", shift=True),
    KeyBinding(name="return", action="select-current"),
    KeyBinding(name="linefeed", action="select-current"),
]


class SelectRenderable(Renderable):
    """Keyboard-navigable option list renderable.

    Usage:
        sel = SelectRenderable(
            options=[
                SelectOption("Option A", value="a", description="First"),
                SelectOption("Option B", value="b", description="Second"),
            ],
            selected_index=0,
        )
        sel.focus()
        sel.handle_key(KeyEvent(key="down"))
        assert sel.get_selected_index() == 1
    """

    __slots__ = (
        "_options",
        "_selected_index",
        "_show_scroll_indicator",
        "_show_description",
        "_wrap_selection",
        "_item_spacing",
        "_fast_scroll_step",
        "_font",
        "_text_color",
        "_focused_bg_color",
        "_focused_text_color",
        "_selected_bg_color",
        "_selected_text_color",
        "_description_color",
        "_selected_description_color",
        "_key_bindings",
        "_key_alias_map",
        "_key_map",
        "_is_destroyed",
        "_raster_dirty",
        "_raster_buffer",
        "_raster_buffer_ptr",
        "_raster_buffer_size",
    )

    def __init__(
        self,
        *,
        options: list[SelectOption] | None = None,
        selected_index: int = 0,
        # Display options
        show_scroll_indicator: bool = False,
        show_description: bool = True,
        wrap_selection: bool = False,
        item_spacing: int = 0,
        fast_scroll_step: int = 5,
        font: str | None = None,
        # Colors
        background_color: s.RGBA | str | None = None,
        text_color: s.RGBA | str | None = None,
        focused_background_color: s.RGBA | str | None = None,
        focused_text_color: s.RGBA | str | None = None,
        selected_background_color: s.RGBA | str | None = None,
        selected_text_color: s.RGBA | str | None = None,
        description_color: s.RGBA | str | None = None,
        selected_description_color: s.RGBA | str | None = None,
        # Key bindings
        key_bindings: list[KeyBinding] | None = None,
        key_alias_map: KeyAliasMap | None = None,
        **kwargs,
    ):
        if background_color is not None and "background_color" not in kwargs:
            kwargs["background_color"] = background_color

        super().__init__(**kwargs)

        self._options: list[SelectOption] = list(options) if options else []

        if self._options:
            self._selected_index = max(0, min(selected_index, len(self._options) - 1))
        else:
            self._selected_index = 0

        # Display options
        self._set_or_bind("_show_scroll_indicator", show_scroll_indicator)
        self._set_or_bind("_show_description", show_description)
        self._wrap_selection = wrap_selection
        self._set_or_bind("_item_spacing", item_spacing)
        self._fast_scroll_step = fast_scroll_step
        self._set_or_bind("_font", font)

        # Colors
        self._set_or_bind("_text_color", text_color, transform=self._parse_color)
        self._set_or_bind(
            "_focused_bg_color", focused_background_color, transform=self._parse_color
        )
        self._set_or_bind("_focused_text_color", focused_text_color, transform=self._parse_color)
        self._set_or_bind(
            "_selected_bg_color", selected_background_color, transform=self._parse_color
        )
        self._set_or_bind("_selected_text_color", selected_text_color, transform=self._parse_color)
        self._set_or_bind("_description_color", description_color, transform=self._parse_color)
        self._set_or_bind(
            "_selected_description_color", selected_description_color, transform=self._parse_color
        )

        self._focusable = True

        self._key_bindings = list(_DEFAULT_SELECT_BINDINGS)
        self._key_alias_map = dict(DEFAULT_KEY_ALIASES)
        if key_bindings:
            self._key_bindings = merge_key_bindings(self._key_bindings, key_bindings)
        if key_alias_map:
            self._key_alias_map = merge_key_aliases(self._key_alias_map, key_alias_map)
        self._key_map = build_key_bindings_map(self._key_bindings, self._key_alias_map)

        self._is_destroyed = False
        self._raster_dirty = True
        self._raster_buffer = None
        self._raster_buffer_ptr = None
        self._raster_buffer_size: tuple[int, int] | None = None

        self._setup_measure_func()

    def get_render_strategy(self) -> RenderStrategy:
        return RenderStrategy.HEAVY_WIDGET

    def mark_dirty(self) -> None:
        if hasattr(self, "_raster_dirty"):
            self._raster_dirty = True
        super().mark_dirty()

    def mark_paint_dirty(self) -> None:
        if hasattr(self, "_raster_dirty"):
            self._raster_dirty = True
        super().mark_paint_dirty()

    @property
    def options(self) -> list[SelectOption]:
        return list(self._options)

    @options.setter
    def options(self, opts: list[SelectOption]) -> None:
        self._options = list(opts) if opts else []
        if self._options:
            self._selected_index = min(self._selected_index, len(self._options) - 1)
        else:
            self._selected_index = 0
        self.mark_dirty()
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()

    @property
    def selected_index(self) -> int:
        return self._selected_index

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        self.set_selected_index(index)

    @property
    def show_scroll_indicator(self) -> bool:
        return self._show_scroll_indicator

    @show_scroll_indicator.setter
    def show_scroll_indicator(self, v: bool) -> None:
        self._show_scroll_indicator = v
        self.mark_paint_dirty()

    @property
    def show_description(self) -> bool:
        return self._show_description

    @show_description.setter
    def show_description(self, v: bool) -> None:
        self._show_description = v
        self.mark_dirty()
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()

    @property
    def wrap_selection(self) -> bool:
        return self._wrap_selection

    @wrap_selection.setter
    def wrap_selection(self, v: bool) -> None:
        self._wrap_selection = v

    @property
    def item_spacing(self) -> int:
        return self._item_spacing

    @item_spacing.setter
    def item_spacing(self, v: int) -> None:
        self._item_spacing = v
        self.mark_dirty()
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()

    @property
    def fast_scroll_step(self) -> int:
        return self._fast_scroll_step

    @fast_scroll_step.setter
    def fast_scroll_step(self, v: int) -> None:
        self._fast_scroll_step = v

    @property
    def font(self) -> str | None:
        return self._font

    @font.setter
    def font(self, v: str | None) -> None:
        self._font = v
        self.mark_paint_dirty()

    @property
    def text_color(self) -> s.RGBA | None:
        return self._text_color

    @text_color.setter
    def text_color(self, v: s.RGBA | str | None) -> None:
        self._text_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def background_color(self) -> s.RGBA | None:
        return self._background_color

    @background_color.setter
    def background_color(self, v: s.RGBA | str | None) -> None:
        self._background_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def focused_background_color(self) -> s.RGBA | None:
        return self._focused_bg_color

    @focused_background_color.setter
    def focused_background_color(self, v: s.RGBA | str | None) -> None:
        self._focused_bg_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def focused_text_color(self) -> s.RGBA | None:
        return self._focused_text_color

    @focused_text_color.setter
    def focused_text_color(self, v: s.RGBA | str | None) -> None:
        self._focused_text_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def selected_background_color(self) -> s.RGBA | None:
        return self._selected_bg_color

    @selected_background_color.setter
    def selected_background_color(self, v: s.RGBA | str | None) -> None:
        self._selected_bg_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def selected_text_color(self) -> s.RGBA | None:
        return self._selected_text_color

    @selected_text_color.setter
    def selected_text_color(self, v: s.RGBA | str | None) -> None:
        self._selected_text_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def description_color(self) -> s.RGBA | None:
        return self._description_color

    @description_color.setter
    def description_color(self, v: s.RGBA | str | None) -> None:
        self._description_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def selected_description_color(self) -> s.RGBA | None:
        return self._selected_description_color

    @selected_description_color.setter
    def selected_description_color(self, v: s.RGBA | str | None) -> None:
        self._selected_description_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def key_bindings(self) -> list[KeyBinding]:
        return list(self._key_bindings)

    @key_bindings.setter
    def key_bindings(self, bindings: list[KeyBinding]) -> None:
        self._key_bindings = merge_key_bindings(_DEFAULT_SELECT_BINDINGS, bindings)
        self._key_map = build_key_bindings_map(self._key_bindings, self._key_alias_map)

    @property
    def key_alias_map(self) -> KeyAliasMap:
        return dict(self._key_alias_map)

    @key_alias_map.setter
    def key_alias_map(self, aliases: KeyAliasMap) -> None:
        self._key_alias_map = merge_key_aliases(DEFAULT_KEY_ALIASES, aliases)
        self._key_map = build_key_bindings_map(self._key_bindings, self._key_alias_map)

    def get_selected_index(self) -> int:
        return self._selected_index

    def get_selected_option(self) -> SelectOption | None:
        if not self._options or self._selected_index >= len(self._options):
            return None
        return self._options[self._selected_index]

    def set_selected_index(self, index: int) -> None:
        if not self._options:
            return
        if index < 0 or index >= len(self._options):
            return
        self._selected_index = index
        self.emit("selectionChanged", index, self._options[index])
        self.mark_paint_dirty()

    def move_up(self, steps: int = 1) -> None:
        if not self._options:
            return
        new_index = self._selected_index - steps
        new_index = new_index % len(self._options) if self._wrap_selection else max(0, new_index)
        self._selected_index = new_index
        option = (
            self._options[self._selected_index]
            if self._selected_index < len(self._options)
            else None
        )
        self.emit("selectionChanged", self._selected_index, option)
        self.mark_paint_dirty()

    def move_down(self, steps: int = 1) -> None:
        if not self._options:
            return
        new_index = self._selected_index + steps
        if self._wrap_selection:
            new_index = new_index % len(self._options)
        else:
            new_index = min(len(self._options) - 1, new_index)
        self._selected_index = new_index
        option = (
            self._options[self._selected_index]
            if self._selected_index < len(self._options)
            else None
        )
        self.emit("selectionChanged", self._selected_index, option)
        self.mark_paint_dirty()

    def select_current(self) -> None:
        if not self._options or self._selected_index >= len(self._options):
            return
        option = self._options[self._selected_index]
        self.emit("itemSelected", self._selected_index, option)

    def on_resize(self, width: int, height: int) -> None:
        self.mark_dirty()

    def handle_key(self, event: KeyEvent) -> bool:
        if event.default_prevented:
            return False

        action = self._lookup_action(event)
        if action:
            return self._dispatch_action(action)

        return False

    def _lookup_action(self, event: KeyEvent) -> str | None:
        return lookup_action(
            event.key,
            event.ctrl,
            event.shift,
            event.alt,
            event.meta,
            self._key_map,
            self._key_alias_map,
        )

    def _dispatch_action(self, action: str) -> bool:
        if action == "move-up":
            self.move_up()
            return True
        if action == "move-down":
            self.move_down()
            return True
        if action == "move-up-fast":
            self.move_up(self._fast_scroll_step)
            return True
        if action == "move-down-fast":
            self.move_down(self._fast_scroll_step)
            return True
        if action == "select-current":
            self.select_current()
            return True
        return False

    def _setup_measure_func(self) -> None:
        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            lines_per_item = 2 if self._show_description else 1
            total_items = len(self._options)
            content_h = total_items * lines_per_item
            if total_items > 1:
                content_h += (total_items - 1) * self._item_spacing

            max_name_len = 1
            for opt in self._options:
                max_name_len = max(max_name_len, len(opt.name))
                if self._show_description and opt.description:
                    max_name_len = max(max_name_len, len(opt.description))

            measured_w = max_name_len
            measured_h = max(1, content_h)

            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(int(width), measured_w)

            return (max(1, measured_w), measured_h)

        self._yoga_node.set_measure_func(measure)

    def _render_select_contents(self, buffer: Buffer) -> None:
        x = self._x
        y = self._y
        w = self._layout_width or 0
        h = self._layout_height or 1

        if w <= 0:
            return

        bg = self._background_color
        if self._focused and self._focused_bg_color:
            bg = self._focused_bg_color
        if bg:
            buffer.fill_rect(x, y, w, h, bg)

        lines_per_item = 2 if self._show_description else 1
        row = 0
        for i, opt in enumerate(self._options):
            if row >= h:
                break
            is_selected = i == self._selected_index
            fg = self._selected_text_color if is_selected else self._text_color
            item_bg = self._selected_bg_color if is_selected else bg

            if item_bg:
                buffer.fill_rect(x, y + row, w, lines_per_item, item_bg)

            name = opt.name[:w] if len(opt.name) > w else opt.name
            buffer.draw_text(name, x, y + row, fg, item_bg)

            if self._show_description and opt.description:
                desc_color = (
                    self._selected_description_color if is_selected else self._description_color
                )
                desc = opt.description[:w] if len(opt.description) > w else opt.description
                if row + 1 < h:
                    buffer.draw_text(desc, x, y + row + 1, desc_color, item_bg)

            row += lines_per_item + self._item_spacing

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        raster = self._ensure_raster_buffer()
        if raster is not None and self._layout_width and self._layout_height:
            if self._raster_dirty:
                raster.clear(0.0)
                raster.push_offset(-self._x, -self._y)
                try:
                    self._render_select_contents(raster)
                finally:
                    raster.pop_offset()
                self._raster_dirty = False

            try:
                buffer._native.draw_frame_buffer(buffer._ptr, self._x, self._y, raster._ptr)
                return
            except Exception:
                pass

        self._render_select_contents(buffer)
        self._raster_dirty = False

    def _ensure_raster_buffer(self) -> Buffer | None:
        width = max(0, int(self._layout_width or 0))
        height = max(0, int(self._layout_height or 0))
        if width <= 0 or height <= 0:
            return None

        if self._raster_buffer_ptr is None:
            ptr = _nb.buffer.create_optimized_buffer(width, height, True, 0, f"select-{self.id}")
            from ..renderer import Buffer as RenderBuffer

            self._raster_buffer_ptr = ptr
            self._raster_buffer = RenderBuffer(ptr, _nb.buffer, _nb.graphics)
            self._raster_buffer_size = (width, height)
            self._raster_dirty = True
            return self._raster_buffer

        if self._raster_buffer_size != (width, height):
            assert self._raster_buffer is not None
            self._raster_buffer.resize(width, height)
            self._raster_buffer_size = (width, height)
            self._raster_dirty = True

        return self._raster_buffer

    def _release_raster_buffer(self) -> None:
        if self._raster_buffer_ptr is None:
            return
        try:
            _nb.buffer.destroy_optimized_buffer(self._raster_buffer_ptr)
        except Exception:
            pass
        finally:
            self._raster_buffer = None
            self._raster_buffer_ptr = None
            self._raster_buffer_size = None

    def destroy(self) -> None:
        self._is_destroyed = True
        self._release_raster_buffer()
        super().destroy()


__all__ = ["SelectRenderable"]
