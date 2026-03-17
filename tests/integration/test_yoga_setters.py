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
# flexGrow
# ---------------------------------------------------------------------------


class TestYogaPropSettersFlexGrow:
    """Yoga Prop Setters - flexGrow"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "flexGrow", 1)
        assert node.flex_grow == 1

    def test_accepts_0(self):
        node = _make_node()
        set_yoga_prop(node, "flexGrow", 0)
        assert node.flex_grow == 0

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "flexGrow", 1)  # set first
        set_yoga_prop(node, "flexGrow", None)
        assert node.flex_grow == 0  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "flexGrow", 1)  # set first
        set_yoga_prop(node, "flexGrow", None)  # None == undefined
        assert node.flex_grow == 0


# ---------------------------------------------------------------------------
# flexShrink
# ---------------------------------------------------------------------------


class TestYogaPropSettersFlexShrink:
    """Yoga Prop Setters - flexShrink"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "flexShrink", 1)
        assert node.flex_shrink == 1

    def test_accepts_0(self):
        node = _make_node()
        set_yoga_prop(node, "flexShrink", 0)
        assert node.flex_shrink == 0

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "flexShrink", 0)  # set first
        set_yoga_prop(node, "flexShrink", None)
        assert node.flex_shrink == 1  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "flexShrink", 0)  # set first
        set_yoga_prop(node, "flexShrink", None)
        assert node.flex_shrink == 1


# ---------------------------------------------------------------------------
# flexDirection
# ---------------------------------------------------------------------------


class TestYogaPropSettersFlexDirection:
    """Yoga Prop Setters - flexDirection"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "flexDirection", "row")
        assert node.flex_direction == yoga.FlexDirection.Row

    def test_accepts_all_valid_values(self):
        node = _make_node()
        for val, expected in [
            ("column", yoga.FlexDirection.Column),
            ("column-reverse", yoga.FlexDirection.ColumnReverse),
            ("row", yoga.FlexDirection.Row),
            ("row-reverse", yoga.FlexDirection.RowReverse),
        ]:
            set_yoga_prop(node, "flexDirection", val)
            assert node.flex_direction == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "flexDirection", "row")
        set_yoga_prop(node, "flexDirection", None)
        assert node.flex_direction == yoga.FlexDirection.Column  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "flexDirection", "row")
        set_yoga_prop(node, "flexDirection", None)
        assert node.flex_direction == yoga.FlexDirection.Column


# ---------------------------------------------------------------------------
# flexWrap
# ---------------------------------------------------------------------------


class TestYogaPropSettersFlexWrap:
    """Yoga Prop Setters - flexWrap"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "flexWrap", "wrap")
        assert node.flex_wrap == yoga.Wrap.Wrap

    def test_accepts_all_valid_values(self):
        node = _make_node()
        for val, expected in [
            ("no-wrap", yoga.Wrap.NoWrap),
            ("wrap", yoga.Wrap.Wrap),
            ("wrap-reverse", yoga.Wrap.WrapReverse),
        ]:
            set_yoga_prop(node, "flexWrap", val)
            assert node.flex_wrap == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "flexWrap", "wrap")
        set_yoga_prop(node, "flexWrap", None)
        assert node.flex_wrap == yoga.Wrap.NoWrap  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "flexWrap", "wrap")
        set_yoga_prop(node, "flexWrap", None)
        assert node.flex_wrap == yoga.Wrap.NoWrap


# ---------------------------------------------------------------------------
# alignItems
# ---------------------------------------------------------------------------


class TestYogaPropSettersAlignItems:
    """Yoga Prop Setters - alignItems"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "alignItems", "center")
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
            set_yoga_prop(node, "alignItems", val)
            assert node.align_items == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "alignItems", "center")
        set_yoga_prop(node, "alignItems", None)
        assert node.align_items == yoga.Align.Stretch  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "alignItems", "center")
        set_yoga_prop(node, "alignItems", None)
        assert node.align_items == yoga.Align.Stretch


# ---------------------------------------------------------------------------
# justifyContent
# ---------------------------------------------------------------------------


class TestYogaPropSettersJustifyContent:
    """Yoga Prop Setters - justifyContent"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "justifyContent", "center")
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
            set_yoga_prop(node, "justifyContent", val)
            assert node.justify_content == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "justifyContent", "center")
        set_yoga_prop(node, "justifyContent", None)
        assert node.justify_content == yoga.Justify.FlexStart  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "justifyContent", "center")
        set_yoga_prop(node, "justifyContent", None)
        assert node.justify_content == yoga.Justify.FlexStart


# ---------------------------------------------------------------------------
# alignSelf
# ---------------------------------------------------------------------------


class TestYogaPropSettersAlignSelf:
    """Yoga Prop Setters - alignSelf"""

    def test_accepts_valid_string(self):
        node = _make_node()
        set_yoga_prop(node, "alignSelf", "center")
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
            set_yoga_prop(node, "alignSelf", val)
            assert node.align_self == expected, f"Failed for {val}"

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "alignSelf", "center")
        set_yoga_prop(node, "alignSelf", None)
        assert node.align_self == yoga.Align.Auto  # default

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "alignSelf", "center")
        set_yoga_prop(node, "alignSelf", None)
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
# flexBasis
# ---------------------------------------------------------------------------


class TestYogaPropSettersFlexBasis:
    """Yoga Prop Setters - flexBasis"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "flexBasis", 100)
        fb = node.flex_basis
        assert fb.value == 100
        assert fb.unit == yoga.Unit.Point

    def test_accepts_auto(self):
        node = _make_node()
        set_yoga_prop(node, "flexBasis", "auto")
        fb = node.flex_basis
        # yoga-python lacks set_flex_basis_auto; NaN assignment yields Undefined
        assert fb.unit == yoga.Unit.Undefined

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "flexBasis", 100)
        set_yoga_prop(node, "flexBasis", None)
        fb = node.flex_basis
        assert fb.unit == yoga.Unit.Undefined

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "flexBasis", 100)
        set_yoga_prop(node, "flexBasis", None)
        fb = node.flex_basis
        assert fb.unit == yoga.Unit.Undefined


# ---------------------------------------------------------------------------
# minWidth
# ---------------------------------------------------------------------------


class TestYogaPropSettersMinWidth:
    """Yoga Prop Setters - minWidth"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "minWidth", 100)
        mw = node.min_width
        assert mw.value == 100
        assert mw.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "minWidth", "50%")
        mw = node.min_width
        assert mw.value == 50
        assert mw.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "minWidth", 100)
        set_yoga_prop(node, "minWidth", None)
        mw = node.min_width
        assert mw.unit == yoga.Unit.Undefined

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "minWidth", 100)
        set_yoga_prop(node, "minWidth", None)
        mw = node.min_width
        assert mw.unit == yoga.Unit.Undefined


# ---------------------------------------------------------------------------
# maxWidth
# ---------------------------------------------------------------------------


class TestYogaPropSettersMaxWidth:
    """Yoga Prop Setters - maxWidth"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "maxWidth", 100)
        mw = node.max_width
        assert mw.value == 100
        assert mw.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "maxWidth", "50%")
        mw = node.max_width
        assert mw.value == 50
        assert mw.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "maxWidth", 100)
        set_yoga_prop(node, "maxWidth", None)
        mw = node.max_width
        assert mw.unit == yoga.Unit.Undefined

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "maxWidth", 100)
        set_yoga_prop(node, "maxWidth", None)
        mw = node.max_width
        assert mw.unit == yoga.Unit.Undefined


# ---------------------------------------------------------------------------
# minHeight
# ---------------------------------------------------------------------------


class TestYogaPropSettersMinHeight:
    """Yoga Prop Setters - minHeight"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "minHeight", 100)
        mh = node.min_height
        assert mh.value == 100
        assert mh.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "minHeight", "50%")
        mh = node.min_height
        assert mh.value == 50
        assert mh.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "minHeight", 100)
        set_yoga_prop(node, "minHeight", None)
        mh = node.min_height
        assert mh.unit == yoga.Unit.Undefined

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "minHeight", 100)
        set_yoga_prop(node, "minHeight", None)
        mh = node.min_height
        assert mh.unit == yoga.Unit.Undefined


# ---------------------------------------------------------------------------
# maxHeight
# ---------------------------------------------------------------------------


class TestYogaPropSettersMaxHeight:
    """Yoga Prop Setters - maxHeight"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "maxHeight", 100)
        mh = node.max_height
        assert mh.value == 100
        assert mh.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "maxHeight", "50%")
        mh = node.max_height
        assert mh.value == 50
        assert mh.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "maxHeight", 100)
        set_yoga_prop(node, "maxHeight", None)
        mh = node.max_height
        assert mh.unit == yoga.Unit.Undefined

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "maxHeight", 100)
        set_yoga_prop(node, "maxHeight", None)
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
# marginX
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginX:
    """Yoga Prop Setters - marginX"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "marginX", 10)
        m = node.get_margin(yoga.Edge.Horizontal)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_auto(self):
        node = _make_node()
        set_yoga_prop(node, "marginX", "auto")
        m = node.get_margin(yoga.Edge.Horizontal)
        assert m.unit == yoga.Unit.Auto

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "marginX", "10%")
        m = node.get_margin(yoga.Edge.Horizontal)
        assert m.value == 10
        assert m.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "marginX", 10)
        set_yoga_prop(node, "marginX", None)
        m = node.get_margin(yoga.Edge.Horizontal)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "marginX", 10)
        set_yoga_prop(node, "marginX", None)
        m = node.get_margin(yoga.Edge.Horizontal)
        assert m.value == 0


# ---------------------------------------------------------------------------
# marginY
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginY:
    """Yoga Prop Setters - marginY"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "marginY", 10)
        m = node.get_margin(yoga.Edge.Vertical)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_auto(self):
        node = _make_node()
        set_yoga_prop(node, "marginY", "auto")
        m = node.get_margin(yoga.Edge.Vertical)
        assert m.unit == yoga.Unit.Auto

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "marginY", "10%")
        m = node.get_margin(yoga.Edge.Vertical)
        assert m.value == 10
        assert m.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "marginY", 10)
        set_yoga_prop(node, "marginY", None)
        m = node.get_margin(yoga.Edge.Vertical)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "marginY", 10)
        set_yoga_prop(node, "marginY", None)
        m = node.get_margin(yoga.Edge.Vertical)
        assert m.value == 0


# ---------------------------------------------------------------------------
# marginTop
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginTop:
    """Yoga Prop Setters - marginTop"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "marginTop", 10)
        m = node.get_margin(yoga.Edge.Top)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "marginTop", 10)
        set_yoga_prop(node, "marginTop", None)
        m = node.get_margin(yoga.Edge.Top)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "marginTop", 10)
        set_yoga_prop(node, "marginTop", None)
        m = node.get_margin(yoga.Edge.Top)
        assert m.value == 0


# ---------------------------------------------------------------------------
# marginRight
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginRight:
    """Yoga Prop Setters - marginRight"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "marginRight", 10)
        m = node.get_margin(yoga.Edge.Right)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "marginRight", 10)
        set_yoga_prop(node, "marginRight", None)
        m = node.get_margin(yoga.Edge.Right)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "marginRight", 10)
        set_yoga_prop(node, "marginRight", None)
        m = node.get_margin(yoga.Edge.Right)
        assert m.value == 0


# ---------------------------------------------------------------------------
# marginBottom
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginBottom:
    """Yoga Prop Setters - marginBottom"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "marginBottom", 10)
        m = node.get_margin(yoga.Edge.Bottom)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "marginBottom", 10)
        set_yoga_prop(node, "marginBottom", None)
        m = node.get_margin(yoga.Edge.Bottom)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "marginBottom", 10)
        set_yoga_prop(node, "marginBottom", None)
        m = node.get_margin(yoga.Edge.Bottom)
        assert m.value == 0


# ---------------------------------------------------------------------------
# marginLeft
# ---------------------------------------------------------------------------


class TestYogaPropSettersMarginLeft:
    """Yoga Prop Setters - marginLeft"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "marginLeft", 10)
        m = node.get_margin(yoga.Edge.Left)
        assert m.value == 10
        assert m.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "marginLeft", 10)
        set_yoga_prop(node, "marginLeft", None)
        m = node.get_margin(yoga.Edge.Left)
        assert m.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "marginLeft", 10)
        set_yoga_prop(node, "marginLeft", None)
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
# paddingX
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingX:
    """Yoga Prop Setters - paddingX"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "paddingX", 10)
        p = node.get_padding(yoga.Edge.Horizontal)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "paddingX", "10%")
        p = node.get_padding(yoga.Edge.Horizontal)
        assert p.value == 10
        assert p.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "paddingX", 10)
        set_yoga_prop(node, "paddingX", None)
        p = node.get_padding(yoga.Edge.Horizontal)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "paddingX", 10)
        set_yoga_prop(node, "paddingX", None)
        p = node.get_padding(yoga.Edge.Horizontal)
        assert p.value == 0


# ---------------------------------------------------------------------------
# paddingY
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingY:
    """Yoga Prop Setters - paddingY"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "paddingY", 10)
        p = node.get_padding(yoga.Edge.Vertical)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_percentage(self):
        node = _make_node()
        set_yoga_prop(node, "paddingY", "10%")
        p = node.get_padding(yoga.Edge.Vertical)
        assert p.value == 10
        assert p.unit == yoga.Unit.Percent

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "paddingY", 10)
        set_yoga_prop(node, "paddingY", None)
        p = node.get_padding(yoga.Edge.Vertical)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "paddingY", 10)
        set_yoga_prop(node, "paddingY", None)
        p = node.get_padding(yoga.Edge.Vertical)
        assert p.value == 0


# ---------------------------------------------------------------------------
# paddingTop
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingTop:
    """Yoga Prop Setters - paddingTop"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "paddingTop", 10)
        p = node.get_padding(yoga.Edge.Top)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "paddingTop", 10)
        set_yoga_prop(node, "paddingTop", None)
        p = node.get_padding(yoga.Edge.Top)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "paddingTop", 10)
        set_yoga_prop(node, "paddingTop", None)
        p = node.get_padding(yoga.Edge.Top)
        assert p.value == 0


# ---------------------------------------------------------------------------
# paddingRight
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingRight:
    """Yoga Prop Setters - paddingRight"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "paddingRight", 10)
        p = node.get_padding(yoga.Edge.Right)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "paddingRight", 10)
        set_yoga_prop(node, "paddingRight", None)
        p = node.get_padding(yoga.Edge.Right)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "paddingRight", 10)
        set_yoga_prop(node, "paddingRight", None)
        p = node.get_padding(yoga.Edge.Right)
        assert p.value == 0


# ---------------------------------------------------------------------------
# paddingBottom
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingBottom:
    """Yoga Prop Setters - paddingBottom"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "paddingBottom", 10)
        p = node.get_padding(yoga.Edge.Bottom)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "paddingBottom", 10)
        set_yoga_prop(node, "paddingBottom", None)
        p = node.get_padding(yoga.Edge.Bottom)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "paddingBottom", 10)
        set_yoga_prop(node, "paddingBottom", None)
        p = node.get_padding(yoga.Edge.Bottom)
        assert p.value == 0


# ---------------------------------------------------------------------------
# paddingLeft
# ---------------------------------------------------------------------------


class TestYogaPropSettersPaddingLeft:
    """Yoga Prop Setters - paddingLeft"""

    def test_accepts_valid_number(self):
        node = _make_node()
        set_yoga_prop(node, "paddingLeft", 10)
        p = node.get_padding(yoga.Edge.Left)
        assert p.value == 10
        assert p.unit == yoga.Unit.Point

    def test_accepts_null(self):
        node = _make_node()
        set_yoga_prop(node, "paddingLeft", 10)
        set_yoga_prop(node, "paddingLeft", None)
        p = node.get_padding(yoga.Edge.Left)
        assert p.value == 0

    def test_accepts_undefined(self):
        node = _make_node()
        set_yoga_prop(node, "paddingLeft", 10)
        set_yoga_prop(node, "paddingLeft", None)
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
