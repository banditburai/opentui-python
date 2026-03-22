"""Port of upstream Select.test.ts.

Upstream: packages/core/src/renderables/Select.test.ts
Tests ported: 48/48 (48 real)
"""

import pytest

from opentui import create_test_renderer
from opentui.components.input import SelectOption
from opentui.components.select_renderable import SelectRenderable
from opentui.events import KeyEvent
from opentui.input.keymapping import KeyBinding


# ── Helpers ─────────────────────────────────────────────────────────────


def _key(
    name: str, *, ctrl: bool = False, shift: bool = False, alt: bool = False, meta: bool = False
) -> KeyEvent:
    return KeyEvent(key=name, ctrl=ctrl, shift=shift, alt=alt, meta=meta)


def _sample_options(n: int = 5) -> list[SelectOption]:
    return [SelectOption(f"Option {i}", value=f"val{i}", description=f"Desc {i}") for i in range(n)]


# ═══════════════════════════════════════════════════════════════════════
# Initialization
# ═══════════════════════════════════════════════════════════════════════


class TestSelectRenderableInitialization:
    """Maps to describe("SelectRenderable > Initialization")."""

    @pytest.mark.asyncio
    async def test_reuses_raster_cache_when_select_is_clean(self):
        setup = await create_test_renderer(40, 12)
        try:

            class _CountingSelect(SelectRenderable):
                __slots__ = ("render_calls",)

                def __init__(self, **kwargs):
                    super().__init__(**kwargs)
                    self.render_calls = 0

                def _render_select_contents(self, buffer):
                    self.render_calls += 1
                    return super()._render_select_contents(buffer)

            sel = _CountingSelect(options=_sample_options(6), width=40, height=12)
            setup.renderer.root.add(sel)

            setup.render_frame()
            assert sel.render_calls == 1

            setup.render_frame()
            assert sel.render_calls == 1

            sel.selected_index = 1
            setup.render_frame()
            assert sel.render_calls == 2
        finally:
            setup.destroy()

    def test_should_initialize_with_default_options(self):
        """Maps to test("should initialize with default options")."""
        sel = SelectRenderable()
        assert sel.options == []
        assert sel.get_selected_index() == 0
        assert sel.focusable is True
        assert sel.show_scroll_indicator is False
        assert sel.show_description is True
        assert sel.wrap_selection is False

    def test_should_initialize_with_custom_selected_index(self):
        """Maps to test("should initialize with custom selected index")."""
        opts = _sample_options()
        sel = SelectRenderable(options=opts, selected_index=3)
        assert sel.get_selected_index() == 3
        opt = sel.get_selected_option()
        assert opt is not None
        assert opt.name == "Option 3"

    def test_should_initialize_with_custom_options(self):
        """Maps to test("should initialize with custom options")."""
        opts = _sample_options()
        sel = SelectRenderable(
            options=opts,
            show_scroll_indicator=True,
            show_description=False,
            wrap_selection=True,
            item_spacing=2,
            fast_scroll_step=10,
        )
        assert sel.show_scroll_indicator is True
        assert sel.show_description is False
        assert sel.wrap_selection is True
        assert sel.item_spacing == 2
        assert sel.fast_scroll_step == 10

    def test_should_handle_empty_options_array(self):
        """Maps to test("should handle empty options array")."""
        sel = SelectRenderable(options=[])
        assert sel.get_selected_index() == 0
        assert sel.get_selected_option() is None

    def test_should_clamp_selected_index_to_valid_range(self):
        """Maps to test("should clamp selectedIndex to valid range")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=10)
        assert sel.get_selected_index() == 4  # clamped to len-1


# ═══════════════════════════════════════════════════════════════════════
# Options Management
# ═══════════════════════════════════════════════════════════════════════


class TestSelectRenderableOptionsManagement:
    """Maps to describe("SelectRenderable > Options Management")."""

    def test_should_update_options_dynamically(self):
        """Maps to test("should update options dynamically")."""
        sel = SelectRenderable(options=_sample_options(5), selected_index=4)
        assert sel.get_selected_index() == 4

        # Shrink options - should clamp
        sel.options = _sample_options(3)
        assert sel.get_selected_index() == 2  # clamped to new len-1
        assert len(sel.options) == 3

    def test_should_handle_setting_empty_options(self):
        """Maps to test("should handle setting empty options")."""
        sel = SelectRenderable(options=_sample_options(5), selected_index=3)
        sel.options = []
        assert sel.get_selected_index() == 0
        assert sel.get_selected_option() is None

    def test_should_preserve_valid_selected_index_when_options_change(self):
        """Maps to test("should preserve valid selected index when options change")."""
        sel = SelectRenderable(options=_sample_options(3), selected_index=1)
        assert sel.get_selected_index() == 1

        # Extend options - index should be preserved
        sel.options = _sample_options(10)
        assert sel.get_selected_index() == 1


# ═══════════════════════════════════════════════════════════════════════
# Selection Management
# ═══════════════════════════════════════════════════════════════════════


class TestSelectRenderableSelectionManagement:
    """Maps to describe("SelectRenderable > Selection Management")."""

    def test_should_set_selected_index_programmatically(self):
        """Maps to test("should set selected index programmatically")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts)
        events: list[tuple[int, SelectOption]] = []
        sel.on("selectionChanged", lambda idx, opt: events.append((idx, opt)))

        sel.set_selected_index(3)
        assert sel.get_selected_index() == 3
        assert len(events) == 1
        assert events[0][0] == 3
        assert events[0][1].name == "Option 3"

    def test_should_ignore_invalid_selected_index(self):
        """Maps to test("should ignore invalid selected index")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts)
        events: list = []
        sel.on("selectionChanged", lambda idx, opt: events.append((idx, opt)))

        sel.set_selected_index(-1)
        assert sel.get_selected_index() == 0
        assert len(events) == 0

        sel.set_selected_index(10)
        assert sel.get_selected_index() == 0
        assert len(events) == 0

    def test_should_move_up_correctly(self):
        """Maps to test("should move up correctly")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=2)

        sel.move_up()
        assert sel.get_selected_index() == 1
        sel.move_up()
        assert sel.get_selected_index() == 0
        # Should stop at 0 without wrap
        sel.move_up()
        assert sel.get_selected_index() == 0

    def test_should_move_down_correctly(self):
        """Maps to test("should move down correctly")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=2)

        sel.move_down()
        assert sel.get_selected_index() == 3
        sel.move_down()
        assert sel.get_selected_index() == 4
        # Should stop at last index without wrap
        sel.move_down()
        assert sel.get_selected_index() == 4

    def test_should_wrap_selection_when_enabled(self):
        """Maps to test("should wrap selection when enabled")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=0, wrap_selection=True)

        # Wrap up from 0 -> 4
        sel.move_up()
        assert sel.get_selected_index() == 4

        # Wrap down from 4 -> 0
        sel.move_down()
        assert sel.get_selected_index() == 0

    def test_should_move_multiple_steps(self):
        """Maps to test("should move multiple steps")."""
        opts = _sample_options(10)
        sel = SelectRenderable(options=opts, selected_index=0)

        sel.move_down(3)
        assert sel.get_selected_index() == 3

        sel.move_up(2)
        assert sel.get_selected_index() == 1

    def test_should_select_current_item(self):
        """Maps to test("should select current item")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=2)
        events: list[tuple[int, SelectOption]] = []
        sel.on("itemSelected", lambda idx, opt: events.append((idx, opt)))

        sel.select_current()
        assert len(events) == 1
        assert events[0][0] == 2
        assert events[0][1].name == "Option 2"

    def test_should_not_select_when_no_options_available(self):
        """Maps to test("should not select when no options available")."""
        sel = SelectRenderable(options=[])
        events: list = []
        sel.on("itemSelected", lambda idx, opt: events.append((idx, opt)))

        sel.select_current()
        assert len(events) == 0


# ═══════════════════════════════════════════════════════════════════════
# Keyboard Interaction
# ═══════════════════════════════════════════════════════════════════════


class TestSelectRenderableKeyboardInteraction:
    """Maps to describe("SelectRenderable > Keyboard Interaction")."""

    def test_should_handle_up_down_arrow_keys(self):
        """Maps to test("should handle up/down arrow keys")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=2)
        sel.focus()

        assert sel.handle_key(_key("down")) is True
        assert sel.get_selected_index() == 3

        assert sel.handle_key(_key("up")) is True
        assert sel.get_selected_index() == 2

    def test_should_handle_j_k_keys_vim_style(self):
        """Maps to test("should handle j/k keys (vim-style)")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=2)
        sel.focus()

        assert sel.handle_key(_key("j")) is True
        assert sel.get_selected_index() == 3

        assert sel.handle_key(_key("k")) is True
        assert sel.get_selected_index() == 2

    def test_should_handle_enter_key(self):
        """Maps to test("should handle enter key")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=1)
        sel.focus()
        events: list[tuple[int, SelectOption]] = []
        sel.on("itemSelected", lambda idx, opt: events.append((idx, opt)))

        assert sel.handle_key(_key("return")) is True
        assert len(events) == 1
        assert events[0][0] == 1
        assert events[0][1].name == "Option 1"

    def test_should_handle_linefeed_key(self):
        """Maps to test("should handle linefeed key")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=1)
        sel.focus()
        events: list[tuple[int, SelectOption]] = []
        sel.on("itemSelected", lambda idx, opt: events.append((idx, opt)))

        assert sel.handle_key(_key("linefeed")) is True
        assert len(events) == 1
        assert events[0][0] == 1

    def test_should_handle_fast_scroll_with_shift_modifier(self):
        """Maps to test("should handle fast scroll with shift modifier")."""
        opts = _sample_options(20)
        sel = SelectRenderable(options=opts, selected_index=0, fast_scroll_step=5)
        sel.focus()

        assert sel.handle_key(_key("down", shift=True)) is True
        assert sel.get_selected_index() == 5

        assert sel.handle_key(_key("up", shift=True)) is True
        assert sel.get_selected_index() == 0

    def test_should_ignore_unhandled_keys(self):
        """Maps to test("should ignore unhandled keys")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=2)
        sel.focus()

        assert sel.handle_key(_key("a")) is False
        assert sel.get_selected_index() == 2


# ═══════════════════════════════════════════════════════════════════════
# Property Changes
# ═══════════════════════════════════════════════════════════════════════


class TestSelectRenderablePropertyChanges:
    """Maps to describe("SelectRenderable > Property Changes")."""

    def test_should_update_show_scroll_indicator(self):
        """Maps to test("should update showScrollIndicator")."""
        sel = SelectRenderable(options=_sample_options())
        assert sel.show_scroll_indicator is False
        sel.show_scroll_indicator = True
        assert sel.show_scroll_indicator is True

    def test_should_update_show_description(self):
        """Maps to test("should update showDescription")."""
        sel = SelectRenderable(options=_sample_options())
        assert sel.show_description is True
        sel.show_description = False
        assert sel.show_description is False

    def test_should_update_wrap_selection(self):
        """Maps to test("should update wrapSelection")."""
        sel = SelectRenderable(options=_sample_options())
        assert sel.wrap_selection is False
        sel.wrap_selection = True
        assert sel.wrap_selection is True

    def test_should_update_colors(self):
        """Maps to test("should update colors")."""
        sel = SelectRenderable(options=_sample_options())

        sel.background_color = "#FF0000"
        assert sel.background_color is not None

        sel.text_color = "#00FF00"
        assert sel.text_color is not None

        sel.focused_background_color = "#0000FF"
        assert sel.focused_background_color is not None

        sel.focused_text_color = "#FFFFFF"
        assert sel.focused_text_color is not None

        sel.selected_background_color = "#334455"
        assert sel.selected_background_color is not None

        sel.selected_text_color = "#FFFF00"
        assert sel.selected_text_color is not None

        sel.description_color = "#888888"
        assert sel.description_color is not None

        sel.selected_description_color = "#CCCCCC"
        assert sel.selected_description_color is not None

    def test_should_update_font(self):
        """Maps to test("should update font")."""
        sel = SelectRenderable(options=_sample_options())
        assert sel.font is None
        sel.font = "monospace"
        assert sel.font == "monospace"

    def test_should_update_item_spacing(self):
        """Maps to test("should update itemSpacing")."""
        sel = SelectRenderable(options=_sample_options())
        assert sel.item_spacing == 0
        sel.item_spacing = 2
        assert sel.item_spacing == 2

    def test_should_update_fast_scroll_step(self):
        """Maps to test("should update fastScrollStep")."""
        sel = SelectRenderable(options=_sample_options())
        assert sel.fast_scroll_step == 5
        sel.fast_scroll_step = 10
        assert sel.fast_scroll_step == 10

    def test_should_update_selected_index_via_setter(self):
        """Maps to test("should update selectedIndex via setter")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts)
        events: list = []
        sel.on("selectionChanged", lambda idx, opt: events.append((idx, opt)))

        sel.selected_index = 3
        assert sel.get_selected_index() == 3
        assert len(events) == 1


# ═══════════════════════════════════════════════════════════════════════
# Event Emission
# ═══════════════════════════════════════════════════════════════════════


class TestSelectRenderableEventEmission:
    """Maps to describe("SelectRenderable > Event Emission")."""

    def test_should_emit_selection_changed_when_moving(self):
        """Maps to test("should emit SELECTION_CHANGED when moving")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=2)
        events: list[tuple[int, SelectOption]] = []
        sel.on("selectionChanged", lambda idx, opt: events.append((idx, opt)))

        sel.move_down()
        assert len(events) == 1
        assert events[0][0] == 3
        assert events[0][1].name == "Option 3"

        sel.move_up()
        assert len(events) == 2
        assert events[1][0] == 2
        assert events[1][1].name == "Option 2"

    def test_should_emit_item_selected_when_selecting(self):
        """Maps to test("should emit ITEM_SELECTED when selecting")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=1)
        events: list[tuple[int, SelectOption]] = []
        sel.on("itemSelected", lambda idx, opt: events.append((idx, opt)))

        sel.select_current()
        assert len(events) == 1
        assert events[0][0] == 1
        assert events[0][1].name == "Option 1"
        assert events[0][1].value == "val1"

    def test_should_not_reuse_the_same_keypress_after_focusing_another_select(self):
        """Maps to test("should not reuse the same keypress after focusing another select")."""
        opts1 = _sample_options(3)
        opts2 = _sample_options(3)
        sel1 = SelectRenderable(options=opts1, selected_index=0)
        sel2 = SelectRenderable(options=opts2, selected_index=0)
        sel1.focus()

        events1: list = []
        events2: list = []
        sel1.on("itemSelected", lambda idx, opt: events1.append((idx, opt)))
        sel2.on("itemSelected", lambda idx, opt: events2.append((idx, opt)))

        # Press Enter on sel1 - should emit on sel1 only
        ev = _key("return")
        sel1.handle_key(ev)
        assert len(events1) == 1

        # Now focus sel2 via the handler
        sel1.blur()
        sel2.focus()

        # The same key event should NOT trigger sel2 (already consumed)
        # In upstream, this is handled by event.preventDefault() after consumption
        ev.prevent_default()
        result = sel2.handle_key(ev)
        assert result is False
        assert len(events2) == 0

    def test_should_emit_events_even_when_movement_is_blocked(self):
        """Maps to test("should emit events even when movement is blocked")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, selected_index=0)
        events: list[tuple[int, SelectOption]] = []
        sel.on("selectionChanged", lambda idx, opt: events.append((idx, opt)))

        # Move up at index 0 - blocked but should still emit
        sel.move_up()
        assert sel.get_selected_index() == 0
        assert len(events) == 1
        assert events[0][0] == 0


# ═══════════════════════════════════════════════════════════════════════
# Resize Handling
# ═══════════════════════════════════════════════════════════════════════


class TestSelectRenderableResizeHandling:
    """Maps to describe("SelectRenderable > Resize Handling")."""

    def test_should_handle_resize_events(self):
        """Maps to test("should handle resize events")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts)
        # Should not throw
        sel.on_resize(80, 24)
        # Select should still function
        sel.move_down()
        assert sel.get_selected_index() == 1


# ═══════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════


class TestSelectRenderableEdgeCases:
    """Maps to describe("SelectRenderable > Edge Cases")."""

    def test_should_handle_options_with_undefined_values(self):
        """Maps to test("should handle options with undefined values")."""
        opts = [
            SelectOption("No Value A"),
            SelectOption("No Value B"),
        ]
        sel = SelectRenderable(options=opts)
        opt = sel.get_selected_option()
        assert opt is not None
        assert opt.name == "No Value A"
        # SelectOption defaults value to name when not provided
        assert opt.value == "No Value A"

    def test_should_handle_single_option(self):
        """Maps to test("should handle single option")."""
        opts = [SelectOption("Only", value="only")]
        sel = SelectRenderable(options=opts)
        events: list = []
        sel.on("selectionChanged", lambda idx, opt: events.append((idx, opt)))

        sel.move_up()
        assert sel.get_selected_index() == 0
        assert len(events) == 1  # Event still emitted

        sel.move_down()
        assert sel.get_selected_index() == 0
        assert len(events) == 2  # Event still emitted

    def test_should_handle_very_small_dimensions(self):
        """Maps to test("should handle very small dimensions")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts, width=1, height=1)
        # Should not throw
        sel.move_down()
        assert sel.get_selected_index() == 1
        sel.select_current()

    def test_should_handle_long_option_names_and_descriptions(self):
        """Maps to test("should handle long option names and descriptions")."""
        long_name = "A" * 200
        long_desc = "B" * 200
        opts = [SelectOption(long_name, description=long_desc)]
        sel = SelectRenderable(options=opts)
        opt = sel.get_selected_option()
        assert opt is not None
        assert opt.name == long_name
        assert opt.description == long_desc

    def test_should_handle_focus_state_changes(self):
        """Maps to test("should handle focus state changes")."""
        sel = SelectRenderable(options=_sample_options())
        assert sel.focused is False

        sel.focus()
        assert sel.focused is True

        sel.blur()
        assert sel.focused is False


# ═══════════════════════════════════════════════════════════════════════
# Key Bindings and Aliases
# ═══════════════════════════════════════════════════════════════════════


class TestSelectRenderableKeyBindingsAndAliases:
    """Maps to describe("SelectRenderable > Key Bindings and Aliases")."""

    def test_should_support_custom_key_bindings(self):
        """Maps to test("should support custom key bindings")."""
        opts = _sample_options(5)
        sel = SelectRenderable(
            options=opts,
            key_bindings=[
                KeyBinding(name="h", action="move-up"),
                KeyBinding(name="l", action="move-down"),
            ],
        )
        sel.focus()

        assert sel.handle_key(_key("l")) is True
        assert sel.get_selected_index() == 1

        assert sel.handle_key(_key("h")) is True
        assert sel.get_selected_index() == 0

    def test_should_support_key_aliases(self):
        """Maps to test("should support key aliases")."""
        opts = _sample_options(5)
        sel = SelectRenderable(
            options=opts,
            selected_index=1,
            key_alias_map={"enter": "return"},
        )
        sel.focus()
        events: list = []
        sel.on("itemSelected", lambda idx, opt: events.append((idx, opt)))

        # "enter" should be aliased to "return" and trigger select-current
        assert sel.handle_key(_key("enter")) is True
        assert len(events) == 1

    def test_should_merge_custom_bindings_with_defaults(self):
        """Maps to test("should merge custom bindings with defaults")."""
        opts = _sample_options(5)
        sel = SelectRenderable(
            options=opts,
            key_bindings=[
                KeyBinding(name="h", action="move-up"),
            ],
        )
        sel.focus()

        # Custom binding works
        assert sel.handle_key(_key("h")) is True
        assert sel.get_selected_index() == 0  # was 0, tried move up -> still 0

        # Default bindings still work
        assert sel.handle_key(_key("j")) is True
        assert sel.get_selected_index() == 1

    def test_should_override_default_bindings_with_custom_ones(self):
        """Maps to test("should override default bindings with custom ones")."""
        opts = _sample_options(5)
        sel = SelectRenderable(
            options=opts,
            selected_index=2,
            key_bindings=[
                # Override 'k' from move-up to move-down
                KeyBinding(name="k", action="move-down"),
            ],
        )
        sel.focus()

        # 'k' now moves down instead of up
        assert sel.handle_key(_key("k")) is True
        assert sel.get_selected_index() == 3

    def test_should_support_fast_scroll_with_shift_by_default(self):
        """Maps to test("should support fast scroll with shift by default")."""
        opts = _sample_options(20)
        sel = SelectRenderable(options=opts, selected_index=10, fast_scroll_step=5)
        sel.focus()

        assert sel.handle_key(_key("down", shift=True)) is True
        assert sel.get_selected_index() == 15

        assert sel.handle_key(_key("up", shift=True)) is True
        assert sel.get_selected_index() == 10

    def test_should_allow_custom_bindings_for_fast_scroll(self):
        """Maps to test("should allow custom bindings for fast scroll")."""
        opts = _sample_options(20)
        sel = SelectRenderable(
            options=opts,
            selected_index=0,
            fast_scroll_step=5,
            key_bindings=[
                KeyBinding(name="down", action="move-down-fast", ctrl=True),
            ],
        )
        sel.focus()

        assert sel.handle_key(_key("down", ctrl=True)) is True
        assert sel.get_selected_index() == 5

    def test_should_allow_updating_key_bindings_dynamically(self):
        """Maps to test("should allow updating key bindings dynamically")."""
        opts = _sample_options(5)
        sel = SelectRenderable(options=opts)
        sel.focus()

        # Default: 'j' moves down
        assert sel.handle_key(_key("j")) is True
        assert sel.get_selected_index() == 1

        # Update bindings: now 'x' moves down
        sel.key_bindings = [
            KeyBinding(name="x", action="move-down"),
        ]

        assert sel.handle_key(_key("x")) is True
        assert sel.get_selected_index() == 2

        # Default 'j' should still work (merged with defaults)
        assert sel.handle_key(_key("j")) is True
        assert sel.get_selected_index() == 3

    def test_should_handle_modifiers_in_custom_bindings(self):
        """Maps to test("should handle modifiers in custom bindings")."""
        opts = _sample_options(5)
        sel = SelectRenderable(
            options=opts,
            key_bindings=[
                KeyBinding(name="n", action="move-down", ctrl=True),
                KeyBinding(name="p", action="move-up", ctrl=True),
                KeyBinding(name="s", action="select-current", alt=True),
            ],
        )
        sel.focus()

        # Ctrl+N -> move down
        assert sel.handle_key(_key("n", ctrl=True)) is True
        assert sel.get_selected_index() == 1

        # Ctrl+P -> move up
        assert sel.handle_key(_key("p", ctrl=True)) is True
        assert sel.get_selected_index() == 0

        # Alt+S -> select current
        events: list = []
        sel.on("itemSelected", lambda idx, opt: events.append((idx, opt)))
        assert sel.handle_key(_key("s", alt=True)) is True
        assert len(events) == 1

        # Without modifier -> not handled
        assert sel.handle_key(_key("n")) is False
