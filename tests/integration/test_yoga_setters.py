"""Port of upstream yoga-setters.test.ts.

Upstream: packages/core/src/tests/yoga-setters.test.ts
Tests: 117

Each test verifies that set_yoga_prop(node, prop_name, value) does not raise
and that the yoga node reflects the expected value after the call.
"""

import yoga

from opentui.layout import set_yoga_prop, create_node


def _make_node() -> yoga.Node:
    """Create a fresh yoga node for testing."""
    return create_node()


# ---------------------------------------------------------------------------
# flex_grow
# ---------------------------------------------------------------------------


class TestYogaPropSettersFlexGrow:
    """Yoga Prop Setters - flex_grow"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "flex_grow", 1)
        assert node.flex_grow == 1

    def test_accepts_0(self):
        node = _make_node()
        set_yoga_prop(node, "flex_grow", 0)
        assert node.flex_grow == 0

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "flex_grow", 1)  # set first
        set_yoga_prop(node, "flex_grow", None)
        assert node.flex_grow == 0  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "flex_grow", 1)  # set first
        set_yoga_prop(node, "flex_grow", None)  # None == undefined
        assert node.flex_grow == 0


# ---------------------------------------------------------------------------
# flex_shrink
# ---------------------------------------------------------------------------


class TestYogaPropSettersFlexShrink:
    """Yoga Prop Setters - flex_shrink"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "flex_shrink", 1)
        assert node.flex_shrink == 1

    def test_accepts_0(self):
        node = _make_node()
        set_yoga_prop(node, "flex_shrink", 0)
        assert node.flex_shrink == 0

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "flex_shrink", 0)  # set first
        set_yoga_prop(node, "flex_shrink", None)
        assert node.flex_shrink == 1  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "flex_shrink", 0)  # set first
        set_yoga_prop(node, "flex_shrink", None)
        assert node.flex_shrink == 1


# ---------------------------------------------------------------------------
# flex_direction
# ---------------------------------------------------------------------------


class TestYogaPropSettersFlexDirection:
    """Yoga Prop Setters - flex_direction"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "flex_direction", "row")
        assert node.flex_direction == yoga.FlexDirection.Row

    def test_accepts_all_valid_values(self):
        node = _make_node()
        for val, expected in [
            ("column", yoga.FlexDirection.Column),
            ("column-reverse", yoga.FlexDirection.ColumnReverse),
            ("row", yoga.FlexDirection.Row),
            ("row-reverse", yoga.FlexDirection.RowReverse),
        ]:
            set_yoga_prop(node, "flex_direction", val)
            assert node.flex_direction == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "flex_direction", "row")
        set_yoga_prop(node, "flex_direction", None)
        assert node.flex_direction == yoga.FlexDirection.Column  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "flex_direction", "row")
        set_yoga_prop(node, "flex_direction", None)
        assert node.flex_direction == yoga.FlexDirection.Column


# ---------------------------------------------------------------------------
# flex_wrap
# ---------------------------------------------------------------------------


class TestYogaPropSettersFlexWrap:
    """Yoga Prop Setters - flex_wrap"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "flex_wrap", "wrap")
        assert node.flex_wrap == yoga.Wrap.Wrap

    def test_accepts_all_valid_values(self):
        node = _make_node()
        for val, expected in [
            ("no-wrap", yoga.Wrap.NoWrap),
            ("wrap", yoga.Wrap.Wrap),
            ("wrap-reverse", yoga.Wrap.WrapReverse),
        ]:
            set_yoga_prop(node, "flex_wrap", val)
            assert node.flex_wrap == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "flex_wrap", "wrap")
        set_yoga_prop(node, "flex_wrap", None)
        assert node.flex_wrap == yoga.Wrap.NoWrap  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "flex_wrap", "wrap")
        set_yoga_prop(node, "flex_wrap", None)
        assert node.flex_wrap == yoga.Wrap.NoWrap


# ---------------------------------------------------------------------------
# align_items
# ---------------------------------------------------------------------------


class TestYogaPropSettersAlignItems:
    """Yoga Prop Setters - align_items"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "align_items", "center")
        assert node.align_items == yoga.Align.Center

    def test_accepts_all_valid_values(self):
        node = _make_node()
        for val, expected in [
            ("auto", yoga.Align.Auto),
            ("flex-start", yoga.Align.FlexStart),
            ("center", yoga.Align.Center),
            ("flex-end", yoga.Align.FlexEnd),
            ("stretch", yoga.Align.Stretch),
            ("baseline", yoga.Align.Baseline),
            ("space-between", yoga.Align.SpaceBetween),
            ("space-around", yoga.Align.SpaceAround),
            ("space-evenly", yoga.Align.SpaceEvenly),
        ]:
            set_yoga_prop(node, "align_items", val)
            assert node.align_items == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "align_items", "center")
        set_yoga_prop(node, "align_items", None)
        assert node.align_items == yoga.Align.Stretch  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "align_items", "center")
        set_yoga_prop(node, "align_items", None)
        assert node.align_items == yoga.Align.Stretch


# ---------------------------------------------------------------------------
# justify_content
# ---------------------------------------------------------------------------


class TestYogaPropSettersJustifyContent:
    """Yoga Prop Setters - justify_content"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "justify_content", "center")
        assert node.justify_content == yoga.Justify.Center

    def test_accepts_all_valid_values(self):
        node = _make_node()
        for val, expected in [
            ("flex-start", yoga.Justify.FlexStart),
            ("center", yoga.Justify.Center),
            ("flex-end", yoga.Justify.FlexEnd),
            ("space-between", yoga.Justify.SpaceBetween),
            ("space-around", yoga.Justify.SpaceAround),
            ("space-evenly", yoga.Justify.SpaceEvenly),
        ]:
            set_yoga_prop(node, "justify_content", val)
            assert node.justify_content == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "justify_content", "center")
        set_yoga_prop(node, "justify_content", None)
        assert node.justify_content == yoga.Justify.FlexStart  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "justify_content", "center")
        set_yoga_prop(node, "justify_content", None)
        assert node.justify_content == yoga.Justify.FlexStart


# ---------------------------------------------------------------------------
# align_self
# ---------------------------------------------------------------------------


class TestYogaPropSettersAlignSelf:
    """Yoga Prop Setters - align_self"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "align_self", "center")
        assert node.align_self == yoga.Align.Center

    def test_accepts_all_valid_values(self):
        node = _make_node()
        for val, expected in [
            ("auto", yoga.Align.Auto),
            ("flex-start", yoga.Align.FlexStart),
            ("center", yoga.Align.Center),
            ("flex-end", yoga.Align.FlexEnd),
            ("stretch", yoga.Align.Stretch),
            ("baseline", yoga.Align.Baseline),
            ("space-between", yoga.Align.SpaceBetween),
            ("space-around", yoga.Align.SpaceAround),
            ("space-evenly", yoga.Align.SpaceEvenly),
        ]:
            set_yoga_prop(node, "align_self", val)
            assert node.align_self == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "align_self", "center")
        set_yoga_prop(node, "align_self", None)
        assert node.align_self == yoga.Align.Auto  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "align_self", "center")
        set_yoga_prop(node, "align_self", None)
        assert node.align_self == yoga.Align.Auto


# ---------------------------------------------------------------------------
# overflow
# ---------------------------------------------------------------------------


class TestYogaPropSettersOverflow:
    """Yoga Prop Setters - overflow"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "overflow", "hidden")
        assert node.overflow == yoga.Overflow.Hidden

    def test_accepts_all_valid_values(self):
        node = _make_node()
        for val, expected in [
            ("visible", yoga.Overflow.Visible),
            ("hidden", yoga.Overflow.Hidden),
            ("scroll", yoga.Overflow.Scroll),
        ]:
            set_yoga_prop(node, "overflow", val)
            assert node.overflow == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "overflow", "hidden")
        set_yoga_prop(node, "overflow", None)
        assert node.overflow == yoga.Overflow.Visible  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "overflow", "hidden")
        set_yoga_prop(node, "overflow", None)
        assert node.overflow == yoga.Overflow.Visible


# ---------------------------------------------------------------------------
# position
# ---------------------------------------------------------------------------


class TestYogaPropSettersPosition:
    """Yoga Prop Setters - position"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "position", "absolute")
        assert node.position_type == yoga.PositionType.Absolute

    def test_accepts_all_valid_values(self):
        node = _make_node()
        for val, expected in [
            ("static", yoga.PositionType.Static),
            ("relative", yoga.PositionType.Relative),
            ("absolute", yoga.PositionType.Absolute),
        ]:
            set_yoga_prop(node, "position", val)
            assert node.position_type == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "position", "absolute")
        set_yoga_prop(node, "position", None)
        assert node.position_type == yoga.PositionType.Relative  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "position", "absolute")
        set_yoga_prop(node, "position", None)
        assert node.position_type == yoga.PositionType.Relative


# ---------------------------------------------------------------------------
# flex_basis
# ---------------------------------------------------------------------------


class TestYogaPropSettersFlexBasis:
    """Yoga Prop Setters - flex_basis"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "flex_basis", 100)
        fb = node.flex_basis
        assert fb.value == 100
        assert fb.unit == yoga.Unit.Point

    def test_accepts_auto(self):
        node = _make_node()
        set_yoga_prop(node, "flex_basis", "auto")
        fb = node.flex_basis
        # yoga-python lacks set_flex_basis_auto; NaN assignment yields Undefined
        assert fb.unit == yoga.Unit.Undefined

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "flex_basis", 100)
        set_yoga_prop(node, "flex_basis", None)
        fb = node.flex_basis
        assert fb.unit == yoga.Unit.Undefined

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "flex_basis", 100)
        set_yoga_prop(node, "flex_basis", None)
        fb = node.flex_basis
        assert fb.unit == yoga.Unit.Undefined


# ---------------------------------------------------------------------------
# min_width
# ---------------------------------------------------------------------------


class TestYogaPropSettersMinWidth:
    """Yoga Prop Setters - min_width"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "min_width", 100)
        mw = node.min_width
        assert mw.value == 100
        assert mw.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "min_width", "50%")
        mw = node.min_width
        assert mw.value == 50
        assert mw.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "min_width", 100)
        set_yoga_prop(node, "min_width", None)
        mw = node.min_width
        assert mw.unit == yoga.Unit.Undefined

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "min_width", 100)
        set_yoga_prop(node, "min_width", None)
        mw = node.min_width
        assert mw.unit == yoga.Unit.Undefined


# ---------------------------------------------------------------------------
# max_width
# ---------------------------------------------------------------------------


class TestYogaPropSettersMaxWidth:
    """Yoga Prop Setters - max_width"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "max_width", 100)
        mw = node.max_width
        assert mw.value == 100
        assert mw.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "max_width", "50%")
        mw = node.max_width
        assert mw.value == 50
        assert mw.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "max_width", 100)
        set_yoga_prop(node, "max_width", None)
        mw = node.max_width
        assert mw.unit == yoga.Unit.Undefined

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "max_width", 100)
        set_yoga_prop(node, "max_width", None)
        mw = node.max_width
        assert mw.unit == yoga.Unit.Undefined


# ---------------------------------------------------------------------------
# min_height
# ---------------------------------------------------------------------------


class TestYogaPropSettersMinHeight:
    """Yoga Prop Setters - min_height"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "min_height", 100)
        mh = node.min_height
        assert mh.value == 100
        assert mh.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "min_height", "50%")
        mh = node.min_height
        assert mh.value == 50
        assert mh.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "min_height", 100)
        set_yoga_prop(node, "min_height", None)
        mh = node.min_height
        assert mh.unit == yoga.Unit.Undefined

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "min_height", 100)
        set_yoga_prop(node, "min_height", None)
        mh = node.min_height
        assert mh.unit == yoga.Unit.Undefined


# ---------------------------------------------------------------------------
# max_height
# ---------------------------------------------------------------------------


class TestYogaPropSettersMaxHeight:
    """Yoga Prop Setters - max_height"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "max_height", 100)
        mh = node.max_height
        assert mh.value == 100
        assert mh.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "max_height", "50%")
        mh = node.max_height
        assert mh.value == 50
        assert mh.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "max_height", 100)
        set_yoga_prop(node, "max_height", None)
        mh = node.max_height
        assert mh.unit == yoga.Unit.Undefined

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "max_height", 100)
        set_yoga_prop(node, "max_height", None)
        mh = node.max_height
        assert mh.unit == yoga.Unit.Undefined


# ---------------------------------------------------------------------------
# margin
# ---------------------------------------------------------------------------


class TestYogaPropSettersMargin:
    """Yoga Prop Setters - margin"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "margin", 10)
        m = node.get_margin(yoga.Edge.All)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_auto(self):
        node = _make_node()
        set_yoga_prop(node, "margin", "auto")
        m = node.get_margin(yoga.Edge.All)
        assert m.unit == yoga.Unit.Auto

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "margin", "10%")
        m = node.get_margin(yoga.Edge.All)
        assert m.value == 10
        assert m.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "margin", 10)
        set_yoga_prop(node, "margin", None)
        m = node.get_margin(yoga.Edge.All)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "margin", 10)
        set_yoga_prop(node, "margin", None)
        m = node.get_margin(yoga.Edge.All)
        assert m.value == 0


# ---------------------------------------------------------------------------
# margin_x
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginX:
    """Yoga Prop Setters - margin_x"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "margin_x", 10)
        m = node.get_margin(yoga.Edge.Horizontal)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_auto(self):
        node = _make_node()
        set_yoga_prop(node, "margin_x", "auto")
        m = node.get_margin(yoga.Edge.Horizontal)
        assert m.unit == yoga.Unit.Auto

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "margin_x", "10%")
        m = node.get_margin(yoga.Edge.Horizontal)
        assert m.value == 10
        assert m.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "margin_x", 10)
        set_yoga_prop(node, "margin_x", None)
        m = node.get_margin(yoga.Edge.Horizontal)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "margin_x", 10)
        set_yoga_prop(node, "margin_x", None)
        m = node.get_margin(yoga.Edge.Horizontal)
        assert m.value == 0


# ---------------------------------------------------------------------------
# margin_y
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginY:
    """Yoga Prop Setters - margin_y"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "margin_y", 10)
        m = node.get_margin(yoga.Edge.Vertical)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_auto(self):
        node = _make_node()
        set_yoga_prop(node, "margin_y", "auto")
        m = node.get_margin(yoga.Edge.Vertical)
        assert m.unit == yoga.Unit.Auto

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "margin_y", "10%")
        m = node.get_margin(yoga.Edge.Vertical)
        assert m.value == 10
        assert m.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "margin_y", 10)
        set_yoga_prop(node, "margin_y", None)
        m = node.get_margin(yoga.Edge.Vertical)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "margin_y", 10)
        set_yoga_prop(node, "margin_y", None)
        m = node.get_margin(yoga.Edge.Vertical)
        assert m.value == 0


# ---------------------------------------------------------------------------
# margin_top
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginTop:
    """Yoga Prop Setters - margin_top"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "margin_top", 10)
        m = node.get_margin(yoga.Edge.Top)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "margin_top", 10)
        set_yoga_prop(node, "margin_top", None)
        m = node.get_margin(yoga.Edge.Top)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "margin_top", 10)
        set_yoga_prop(node, "margin_top", None)
        m = node.get_margin(yoga.Edge.Top)
        assert m.value == 0


# ---------------------------------------------------------------------------
# margin_right
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginRight:
    """Yoga Prop Setters - margin_right"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "margin_right", 10)
        m = node.get_margin(yoga.Edge.Right)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "margin_right", 10)
        set_yoga_prop(node, "margin_right", None)
        m = node.get_margin(yoga.Edge.Right)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "margin_right", 10)
        set_yoga_prop(node, "margin_right", None)
        m = node.get_margin(yoga.Edge.Right)
        assert m.value == 0


# ---------------------------------------------------------------------------
# margin_bottom
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginBottom:
    """Yoga Prop Setters - margin_bottom"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "margin_bottom", 10)
        m = node.get_margin(yoga.Edge.Bottom)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "margin_bottom", 10)
        set_yoga_prop(node, "margin_bottom", None)
        m = node.get_margin(yoga.Edge.Bottom)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "margin_bottom", 10)
        set_yoga_prop(node, "margin_bottom", None)
        m = node.get_margin(yoga.Edge.Bottom)
        assert m.value == 0


# ---------------------------------------------------------------------------
# margin_left
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginLeft:
    """Yoga Prop Setters - margin_left"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "margin_left", 10)
        m = node.get_margin(yoga.Edge.Left)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "margin_left", 10)
        set_yoga_prop(node, "margin_left", None)
        m = node.get_margin(yoga.Edge.Left)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "margin_left", 10)
        set_yoga_prop(node, "margin_left", None)
        m = node.get_margin(yoga.Edge.Left)
        assert m.value == 0


# ---------------------------------------------------------------------------
# padding
# ---------------------------------------------------------------------------


class TestYogaPropSettersPadding:
    """Yoga Prop Setters - padding"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "padding", 10)
        p = node.get_padding(yoga.Edge.All)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "padding", "10%")
        p = node.get_padding(yoga.Edge.All)
        assert p.value == 10
        assert p.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "padding", 10)
        set_yoga_prop(node, "padding", None)
        p = node.get_padding(yoga.Edge.All)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "padding", 10)
        set_yoga_prop(node, "padding", None)
        p = node.get_padding(yoga.Edge.All)
        assert p.value == 0


# ---------------------------------------------------------------------------
# padding_x
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingX:
    """Yoga Prop Setters - padding_x"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "padding_x", 10)
        p = node.get_padding(yoga.Edge.Horizontal)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "padding_x", "10%")
        p = node.get_padding(yoga.Edge.Horizontal)
        assert p.value == 10
        assert p.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "padding_x", 10)
        set_yoga_prop(node, "padding_x", None)
        p = node.get_padding(yoga.Edge.Horizontal)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "padding_x", 10)
        set_yoga_prop(node, "padding_x", None)
        p = node.get_padding(yoga.Edge.Horizontal)
        assert p.value == 0


# ---------------------------------------------------------------------------
# padding_y
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingY:
    """Yoga Prop Setters - padding_y"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "padding_y", 10)
        p = node.get_padding(yoga.Edge.Vertical)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "padding_y", "10%")
        p = node.get_padding(yoga.Edge.Vertical)
        assert p.value == 10
        assert p.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "padding_y", 10)
        set_yoga_prop(node, "padding_y", None)
        p = node.get_padding(yoga.Edge.Vertical)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "padding_y", 10)
        set_yoga_prop(node, "padding_y", None)
        p = node.get_padding(yoga.Edge.Vertical)
        assert p.value == 0


# ---------------------------------------------------------------------------
# padding_top
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingTop:
    """Yoga Prop Setters - padding_top"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "padding_top", 10)
        p = node.get_padding(yoga.Edge.Top)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "padding_top", 10)
        set_yoga_prop(node, "padding_top", None)
        p = node.get_padding(yoga.Edge.Top)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "padding_top", 10)
        set_yoga_prop(node, "padding_top", None)
        p = node.get_padding(yoga.Edge.Top)
        assert p.value == 0


# ---------------------------------------------------------------------------
# padding_right
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingRight:
    """Yoga Prop Setters - padding_right"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "padding_right", 10)
        p = node.get_padding(yoga.Edge.Right)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "padding_right", 10)
        set_yoga_prop(node, "padding_right", None)
        p = node.get_padding(yoga.Edge.Right)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "padding_right", 10)
        set_yoga_prop(node, "padding_right", None)
        p = node.get_padding(yoga.Edge.Right)
        assert p.value == 0


# ---------------------------------------------------------------------------
# padding_bottom
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingBottom:
    """Yoga Prop Setters - padding_bottom"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "padding_bottom", 10)
        p = node.get_padding(yoga.Edge.Bottom)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "padding_bottom", 10)
        set_yoga_prop(node, "padding_bottom", None)
        p = node.get_padding(yoga.Edge.Bottom)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "padding_bottom", 10)
        set_yoga_prop(node, "padding_bottom", None)
        p = node.get_padding(yoga.Edge.Bottom)
        assert p.value == 0


# ---------------------------------------------------------------------------
# padding_left
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingLeft:
    """Yoga Prop Setters - padding_left"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "padding_left", 10)
        p = node.get_padding(yoga.Edge.Left)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "padding_left", 10)
        set_yoga_prop(node, "padding_left", None)
        p = node.get_padding(yoga.Edge.Left)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "padding_left", 10)
        set_yoga_prop(node, "padding_left", None)
        p = node.get_padding(yoga.Edge.Left)
        assert p.value == 0


# ---------------------------------------------------------------------------
# width
# ---------------------------------------------------------------------------


class TestYogaPropSettersWidth:
    """Yoga Prop Setters - width"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "width", 100)
        w = node.width
        assert w.value == 100
        assert w.unit == yoga.Unit.Point

    def test_accepts_auto(self):
        node = _make_node()
        set_yoga_prop(node, "width", "auto")
        w = node.width
        assert w.unit == yoga.Unit.Auto

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "width", "50%")
        w = node.width
        assert w.value == 50
        assert w.unit == yoga.Unit.Percent

    def test_handles_null(self):
        node = _make_node()
        set_yoga_prop(node, "width", 100)
        set_yoga_prop(node, "width", None)
        w = node.width
        assert w.unit == yoga.Unit.Auto

    def test_handles_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "width", 100)
        set_yoga_prop(node, "width", None)
        w = node.width
        assert w.unit == yoga.Unit.Auto


# ---------------------------------------------------------------------------
# height
# ---------------------------------------------------------------------------


class TestYogaPropSettersHeight:
    """Yoga Prop Setters - height"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "height", 100)
        h = node.height
        assert h.value == 100
        assert h.unit == yoga.Unit.Point

    def test_accepts_auto(self):
        node = _make_node()
        set_yoga_prop(node, "height", "auto")
        h = node.height
        assert h.unit == yoga.Unit.Auto

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "height", "50%")
        h = node.height
        assert h.value == 50
        assert h.unit == yoga.Unit.Percent

    def test_handles_null(self):
        node = _make_node()
        set_yoga_prop(node, "height", 100)
        set_yoga_prop(node, "height", None)
        h = node.height
        assert h.unit == yoga.Unit.Auto

    def test_handles_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "height", 100)
        set_yoga_prop(node, "height", None)
        h = node.height
        assert h.unit == yoga.Unit.Auto
