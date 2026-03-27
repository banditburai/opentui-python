"""Tests for the Select dropdown component.

Upstream: N/A (Python-specific)
"""

from opentui.components.select import Select, SelectOption


class TestSelectOption:
    def test_basic_construction(self):
        opt = SelectOption("Option A")
        assert opt.name == "Option A"
        assert opt.value == "Option A"
        assert opt.description is None

    def test_custom_value(self):
        opt = SelectOption("Display", value=42)
        assert opt.name == "Display"
        assert opt.value == 42

    def test_description(self):
        opt = SelectOption("Opt", description="A helpful description")
        assert opt.description == "A helpful description"

    def test_none_value_defaults_to_name(self):
        opt = SelectOption("Fallback", value=None)
        assert opt.value == "Fallback"


class TestSelectConstruction:
    def test_empty_construction(self):
        sel = Select()
        assert sel.options == []
        assert sel.selected_index == -1
        assert sel.selected is None

    def test_with_options(self):
        opts = [SelectOption("A", value=1), SelectOption("B", value=2)]
        sel = Select(options=opts)
        assert len(sel.options) == 2
        assert sel.selected_index == -1

    def test_preselected_value(self):
        opts = [SelectOption("A", value=1), SelectOption("B", value=2)]
        sel = Select(options=opts, selected=2)
        assert sel.selected_index == 1
        assert sel.selected is opts[1]

    def test_preselected_missing_value(self):
        opts = [SelectOption("A", value=1)]
        sel = Select(options=opts, selected=999)
        assert sel.selected_index == -1
        assert sel.selected is None

    def test_preselected_first_match(self):
        opts = [
            SelectOption("First", value="x"),
            SelectOption("Second", value="x"),
        ]
        sel = Select(options=opts, selected="x")
        assert sel.selected_index == 0


class TestSelectBehavior:
    def test_select_valid_index(self):
        opts = [SelectOption("A"), SelectOption("B"), SelectOption("C")]
        sel = Select(options=opts)
        sel.select(1)
        assert sel.selected_index == 1
        assert sel.selected is opts[1]

    def test_select_out_of_range_no_change(self):
        opts = [SelectOption("A")]
        sel = Select(options=opts)
        sel.select(5)
        assert sel.selected_index == -1

    def test_select_negative_no_change(self):
        opts = [SelectOption("A")]
        sel = Select(options=opts)
        sel.select(-1)
        assert sel.selected_index == -1

    def test_on_change_callback(self):
        calls = []
        opts = [SelectOption("A", value=10), SelectOption("B", value=20)]
        sel = Select(options=opts, on_change=lambda idx, opt: calls.append((idx, opt)))
        sel.select(0)
        assert len(calls) == 1
        assert calls[0] == (0, opts[0])

    def test_on_select_callback(self):
        calls = []
        opts = [SelectOption("A"), SelectOption("B")]
        sel = Select(options=opts, on_select=lambda idx, opt: calls.append((idx, opt)))
        sel.select(1)
        assert len(calls) == 1
        assert calls[0] == (1, opts[1])

    def test_both_callbacks_fire(self):
        change_calls = []
        select_calls = []
        opts = [SelectOption("A")]
        sel = Select(
            options=opts,
            on_change=lambda idx, opt: change_calls.append(idx),
            on_select=lambda idx, opt: select_calls.append(idx),
        )
        sel.select(0)
        assert change_calls == [0]
        assert select_calls == [0]

    def test_selected_property_with_valid_index(self):
        opts = [SelectOption("X", value="val")]
        sel = Select(options=opts)
        sel.select(0)
        assert sel.selected.name == "X"
        assert sel.selected.value == "val"

    def test_selected_property_returns_none_when_unset(self):
        sel = Select(options=[SelectOption("A")])
        assert sel.selected is None


class TestSelectRender:
    """Test render output using a minimal buffer mock."""

    class _MockBuffer:
        def __init__(self, width=80, height=24):
            self.width = width
            self.height = height
            self.texts = []
            self.rects = []

        def draw_text(self, text, x, y, fg=None, bg=None, *args, **kwargs):
            self.texts.append((text, x, y))

        def fill_rect(self, x, y, w, h, color):
            self.rects.append((x, y, w, h))

    def test_render_unselected_shows_placeholder(self):
        sel = Select(options=[SelectOption("A")])
        buf = self._MockBuffer()
        sel._visible = True
        sel._x = 0
        sel._y = 0
        sel._padding_left = 0
        sel._padding_top = 0
        sel._layout_width = 40
        sel._background_color = None
        sel.render(buf)
        assert any("Select..." in t[0] for t in buf.texts)

    def test_render_selected_shows_name(self):
        opts = [SelectOption("My Choice", value=1)]
        sel = Select(options=opts, selected=1)
        buf = self._MockBuffer()
        sel._visible = True
        sel._x = 0
        sel._y = 0
        sel._padding_left = 0
        sel._padding_top = 0
        sel._layout_width = 40
        sel._background_color = None
        sel.render(buf)
        assert any("My Choice" in t[0] for t in buf.texts)

    def test_render_invisible_draws_nothing(self):
        sel = Select(options=[SelectOption("A")])
        buf = self._MockBuffer()
        sel._visible = False
        sel.render(buf)
        assert buf.texts == []

    def test_render_expanded_shows_options(self):
        opts = [SelectOption("A"), SelectOption("B"), SelectOption("C")]
        sel = Select(options=opts)
        sel._expanded = True
        sel._visible = True
        sel._x = 0
        sel._y = 0
        sel._padding_left = 0
        sel._padding_top = 0
        sel._layout_width = 40
        sel._background_color = None
        buf = self._MockBuffer()
        sel.render(buf)
        # Header + 3 option lines
        assert len(buf.texts) >= 4
        names = [t[0] for t in buf.texts]
        assert any("A" in n for n in names)
        assert any("B" in n for n in names)
        assert any("C" in n for n in names)

    def test_render_truncates_long_option_names(self):
        opts = [SelectOption("A" * 100)]
        sel = Select(options=opts, selected="A" * 100)
        sel._visible = True
        sel._x = 0
        sel._y = 0
        sel._padding_left = 0
        sel._padding_top = 0
        sel._layout_width = 20
        sel._background_color = None
        buf = self._MockBuffer()
        sel.render(buf)
        # Rendered text should be truncated to fit width
        for text, _, _ in buf.texts:
            assert len(text) <= 20
