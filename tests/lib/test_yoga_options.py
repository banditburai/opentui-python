"""Port of upstream yoga.options.test.ts.

Upstream: packages/core/src/lib/yoga.options.test.ts
Tests ported: 136/136 (0 skipped)
"""

import yoga

from opentui.layout import (
    parse_align,
    parse_align_items,
    parse_box_sizing,
    parse_dimension,
    parse_direction,
    parse_display,
    parse_edge,
    parse_flex_direction,
    parse_gutter,
    parse_justify,
    parse_log_level,
    parse_measure_mode,
    parse_overflow,
    parse_position_type,
    parse_unit,
    parse_wrap,
)


class TestParseBoxSizing:
    """parseBoxSizing"""

    def test_parses_border_box(self):
        assert parse_box_sizing("border-box") == yoga.BoxSizing.BorderBox

    def test_parses_content_box(self):
        assert parse_box_sizing("content-box") == yoga.BoxSizing.ContentBox

    def test_handles_uppercase(self):
        assert parse_box_sizing("BORDER-BOX") == yoga.BoxSizing.BorderBox
        assert parse_box_sizing("CONTENT-BOX") == yoga.BoxSizing.ContentBox

    def test_returns_default_for_invalid_value(self):
        assert parse_box_sizing("invalid") == yoga.BoxSizing.BorderBox

    def test_handles_null(self):
        assert parse_box_sizing(None) == yoga.BoxSizing.BorderBox

    def test_handles_undefined(self):
        # Python None maps to both JS null and undefined
        assert parse_box_sizing(None) == yoga.BoxSizing.BorderBox


class TestParseDimension:
    """parseDimension"""

    def test_parses_width(self):
        assert parse_dimension("width") == yoga.Dimension.Width

    def test_parses_height(self):
        assert parse_dimension("height") == yoga.Dimension.Height

    def test_handles_uppercase(self):
        assert parse_dimension("WIDTH") == yoga.Dimension.Width
        assert parse_dimension("HEIGHT") == yoga.Dimension.Height

    def test_returns_default_for_invalid_value(self):
        assert parse_dimension("invalid") == yoga.Dimension.Width

    def test_handles_null(self):
        assert parse_dimension(None) == yoga.Dimension.Width

    def test_handles_undefined(self):
        assert parse_dimension(None) == yoga.Dimension.Width


class TestParseDirection:
    """parseDirection"""

    def test_parses_inherit(self):
        assert parse_direction("inherit") == yoga.Direction.Inherit

    def test_parses_ltr(self):
        assert parse_direction("ltr") == yoga.Direction.LTR

    def test_parses_rtl(self):
        assert parse_direction("rtl") == yoga.Direction.RTL

    def test_handles_uppercase(self):
        assert parse_direction("INHERIT") == yoga.Direction.Inherit
        assert parse_direction("LTR") == yoga.Direction.LTR
        assert parse_direction("RTL") == yoga.Direction.RTL

    def test_returns_default_for_invalid_value(self):
        assert parse_direction("invalid") == yoga.Direction.LTR

    def test_handles_null(self):
        assert parse_direction(None) == yoga.Direction.LTR

    def test_handles_undefined(self):
        assert parse_direction(None) == yoga.Direction.LTR


class TestParseDisplay:
    """parseDisplay"""

    def test_parses_flex(self):
        assert parse_display("flex") == yoga.Display.Flex

    def test_parses_none(self):
        assert parse_display("none") == yoga.Display.None_

    def test_parses_contents(self):
        assert parse_display("contents") == yoga.Display.Contents

    def test_handles_uppercase(self):
        assert parse_display("FLEX") == yoga.Display.Flex
        assert parse_display("NONE") == yoga.Display.None_
        assert parse_display("CONTENTS") == yoga.Display.Contents

    def test_returns_default_for_invalid_value(self):
        assert parse_display("invalid") == yoga.Display.Flex

    def test_handles_null(self):
        assert parse_display(None) == yoga.Display.Flex

    def test_handles_undefined(self):
        assert parse_display(None) == yoga.Display.Flex


class TestParseEdge:
    """parseEdge"""

    def test_parses_left(self):
        assert parse_edge("left") == yoga.Edge.Left

    def test_parses_top(self):
        assert parse_edge("top") == yoga.Edge.Top

    def test_parses_right(self):
        assert parse_edge("right") == yoga.Edge.Right

    def test_parses_bottom(self):
        assert parse_edge("bottom") == yoga.Edge.Bottom

    def test_parses_start(self):
        assert parse_edge("start") == yoga.Edge.Start

    def test_parses_end(self):
        assert parse_edge("end") == yoga.Edge.End

    def test_parses_horizontal(self):
        assert parse_edge("horizontal") == yoga.Edge.Horizontal

    def test_parses_vertical(self):
        assert parse_edge("vertical") == yoga.Edge.Vertical

    def test_parses_all(self):
        assert parse_edge("all") == yoga.Edge.All

    def test_handles_uppercase(self):
        assert parse_edge("LEFT") == yoga.Edge.Left
        assert parse_edge("TOP") == yoga.Edge.Top

    def test_returns_default_for_invalid_value(self):
        assert parse_edge("invalid") == yoga.Edge.All

    def test_handles_null(self):
        assert parse_edge(None) == yoga.Edge.All

    def test_handles_undefined(self):
        assert parse_edge(None) == yoga.Edge.All


class TestParseGutter:
    """parseGutter"""

    def test_parses_column(self):
        assert parse_gutter("column") == yoga.Gutter.Column

    def test_parses_row(self):
        assert parse_gutter("row") == yoga.Gutter.Row

    def test_parses_all(self):
        assert parse_gutter("all") == yoga.Gutter.All

    def test_handles_uppercase(self):
        assert parse_gutter("COLUMN") == yoga.Gutter.Column
        assert parse_gutter("ROW") == yoga.Gutter.Row
        assert parse_gutter("ALL") == yoga.Gutter.All

    def test_returns_default_for_invalid_value(self):
        assert parse_gutter("invalid") == yoga.Gutter.All

    def test_handles_null(self):
        assert parse_gutter(None) == yoga.Gutter.All

    def test_handles_undefined(self):
        assert parse_gutter(None) == yoga.Gutter.All


class TestParseLogLevel:
    """parseLogLevel"""

    def test_parses_error(self):
        assert parse_log_level("error") == yoga.LogLevel.Error

    def test_parses_warn(self):
        assert parse_log_level("warn") == yoga.LogLevel.Warn

    def test_parses_info(self):
        assert parse_log_level("info") == yoga.LogLevel.Info

    def test_parses_debug(self):
        assert parse_log_level("debug") == yoga.LogLevel.Debug

    def test_parses_verbose(self):
        assert parse_log_level("verbose") == yoga.LogLevel.Verbose

    def test_parses_fatal(self):
        assert parse_log_level("fatal") == yoga.LogLevel.Fatal

    def test_handles_uppercase(self):
        assert parse_log_level("ERROR") == yoga.LogLevel.Error
        assert parse_log_level("WARN") == yoga.LogLevel.Warn
        assert parse_log_level("INFO") == yoga.LogLevel.Info

    def test_returns_default_for_invalid_value(self):
        assert parse_log_level("invalid") == yoga.LogLevel.Info

    def test_handles_null(self):
        assert parse_log_level(None) == yoga.LogLevel.Info

    def test_handles_undefined(self):
        assert parse_log_level(None) == yoga.LogLevel.Info


class TestParseMeasureMode:
    """parseMeasureMode"""

    def test_parses_undefined(self):
        assert parse_measure_mode("undefined") == yoga.MeasureMode.Undefined

    def test_parses_exactly(self):
        assert parse_measure_mode("exactly") == yoga.MeasureMode.Exactly

    def test_parses_at_most(self):
        assert parse_measure_mode("at-most") == yoga.MeasureMode.AtMost

    def test_handles_uppercase(self):
        assert parse_measure_mode("UNDEFINED") == yoga.MeasureMode.Undefined
        assert parse_measure_mode("EXACTLY") == yoga.MeasureMode.Exactly
        assert parse_measure_mode("AT-MOST") == yoga.MeasureMode.AtMost

    def test_returns_default_for_invalid_value(self):
        assert parse_measure_mode("invalid") == yoga.MeasureMode.Undefined

    def test_handles_null(self):
        assert parse_measure_mode(None) == yoga.MeasureMode.Undefined

    def test_handles_undefined_value(self):
        assert parse_measure_mode(None) == yoga.MeasureMode.Undefined


class TestParseUnit:
    """parseUnit"""

    def test_parses_undefined(self):
        assert parse_unit("undefined") == yoga.Unit.Undefined

    def test_parses_point(self):
        assert parse_unit("point") == yoga.Unit.Point

    def test_parses_percent(self):
        assert parse_unit("percent") == yoga.Unit.Percent

    def test_parses_auto(self):
        assert parse_unit("auto") == yoga.Unit.Auto

    def test_handles_uppercase(self):
        assert parse_unit("UNDEFINED") == yoga.Unit.Undefined
        assert parse_unit("POINT") == yoga.Unit.Point
        assert parse_unit("PERCENT") == yoga.Unit.Percent
        assert parse_unit("AUTO") == yoga.Unit.Auto

    def test_returns_default_for_invalid_value(self):
        assert parse_unit("invalid") == yoga.Unit.Point

    def test_handles_null(self):
        assert parse_unit(None) == yoga.Unit.Point

    def test_handles_undefined_value(self):
        assert parse_unit(None) == yoga.Unit.Point


class TestParseAlign:
    """parseAlign"""

    def test_parses_auto(self):
        assert parse_align("auto") == yoga.Align.Auto

    def test_parses_flex_start(self):
        assert parse_align("flex-start") == yoga.Align.FlexStart

    def test_parses_center(self):
        assert parse_align("center") == yoga.Align.Center

    def test_parses_flex_end(self):
        assert parse_align("flex-end") == yoga.Align.FlexEnd

    def test_parses_stretch(self):
        assert parse_align("stretch") == yoga.Align.Stretch

    def test_parses_baseline(self):
        assert parse_align("baseline") == yoga.Align.Baseline

    def test_parses_space_between(self):
        assert parse_align("space-between") == yoga.Align.SpaceBetween

    def test_parses_space_around(self):
        assert parse_align("space-around") == yoga.Align.SpaceAround

    def test_parses_space_evenly(self):
        assert parse_align("space-evenly") == yoga.Align.SpaceEvenly

    def test_handles_null(self):
        assert parse_align(None) == yoga.Align.Auto

    def test_handles_undefined(self):
        assert parse_align(None) == yoga.Align.Auto

    def test_handles_uppercase(self):
        assert parse_align("CENTER") == yoga.Align.Center

    def test_returns_default_for_invalid_value(self):
        assert parse_align("invalid") == yoga.Align.Auto


class TestParseAlignItems:
    """parseAlignItems"""

    def test_parses_auto(self):
        assert parse_align_items("auto") == yoga.Align.Auto

    def test_parses_flex_start(self):
        assert parse_align_items("flex-start") == yoga.Align.FlexStart

    def test_parses_center(self):
        assert parse_align_items("center") == yoga.Align.Center

    def test_parses_flex_end(self):
        assert parse_align_items("flex-end") == yoga.Align.FlexEnd

    def test_parses_stretch(self):
        assert parse_align_items("stretch") == yoga.Align.Stretch

    def test_parses_baseline(self):
        assert parse_align_items("baseline") == yoga.Align.Baseline

    def test_parses_space_between(self):
        assert parse_align_items("space-between") == yoga.Align.SpaceBetween

    def test_parses_space_around(self):
        assert parse_align_items("space-around") == yoga.Align.SpaceAround

    def test_parses_space_evenly(self):
        assert parse_align_items("space-evenly") == yoga.Align.SpaceEvenly

    def test_returns_stretch_for_null(self):
        assert parse_align_items(None) == yoga.Align.Stretch

    def test_returns_stretch_for_undefined(self):
        assert parse_align_items(None) == yoga.Align.Stretch

    def test_handles_uppercase(self):
        assert parse_align_items("CENTER") == yoga.Align.Center

    def test_returns_stretch_for_invalid_value(self):
        assert parse_align_items("invalid") == yoga.Align.Stretch


class TestParseFlexDirection:
    """parseFlexDirection"""

    def test_parses_column(self):
        assert parse_flex_direction("column") == yoga.FlexDirection.Column

    def test_parses_column_reverse(self):
        assert parse_flex_direction("column-reverse") == yoga.FlexDirection.ColumnReverse

    def test_parses_row(self):
        assert parse_flex_direction("row") == yoga.FlexDirection.Row

    def test_parses_row_reverse(self):
        assert parse_flex_direction("row-reverse") == yoga.FlexDirection.RowReverse

    def test_handles_null(self):
        assert parse_flex_direction(None) == yoga.FlexDirection.Column

    def test_handles_undefined(self):
        assert parse_flex_direction(None) == yoga.FlexDirection.Column

    def test_handles_uppercase(self):
        assert parse_flex_direction("ROW") == yoga.FlexDirection.Row

    def test_returns_default_for_invalid_value(self):
        assert parse_flex_direction("invalid") == yoga.FlexDirection.Column


class TestParseJustify:
    """parseJustify"""

    def test_parses_flex_start(self):
        assert parse_justify("flex-start") == yoga.Justify.FlexStart

    def test_parses_center(self):
        assert parse_justify("center") == yoga.Justify.Center

    def test_parses_flex_end(self):
        assert parse_justify("flex-end") == yoga.Justify.FlexEnd

    def test_parses_space_between(self):
        assert parse_justify("space-between") == yoga.Justify.SpaceBetween

    def test_parses_space_around(self):
        assert parse_justify("space-around") == yoga.Justify.SpaceAround

    def test_parses_space_evenly(self):
        assert parse_justify("space-evenly") == yoga.Justify.SpaceEvenly

    def test_handles_null(self):
        assert parse_justify(None) == yoga.Justify.FlexStart

    def test_handles_undefined(self):
        assert parse_justify(None) == yoga.Justify.FlexStart

    def test_handles_uppercase(self):
        assert parse_justify("CENTER") == yoga.Justify.Center

    def test_returns_default_for_invalid_value(self):
        assert parse_justify("invalid") == yoga.Justify.FlexStart


class TestParseOverflow:
    """parseOverflow"""

    def test_parses_visible(self):
        assert parse_overflow("visible") == yoga.Overflow.Visible

    def test_parses_hidden(self):
        assert parse_overflow("hidden") == yoga.Overflow.Hidden

    def test_parses_scroll(self):
        assert parse_overflow("scroll") == yoga.Overflow.Scroll

    def test_handles_null(self):
        assert parse_overflow(None) == yoga.Overflow.Visible

    def test_handles_undefined(self):
        assert parse_overflow(None) == yoga.Overflow.Visible

    def test_handles_uppercase(self):
        assert parse_overflow("HIDDEN") == yoga.Overflow.Hidden

    def test_returns_default_for_invalid_value(self):
        assert parse_overflow("invalid") == yoga.Overflow.Visible


class TestParsePositionType:
    """parsePositionType"""

    def test_parses_static(self):
        assert parse_position_type("static") == yoga.PositionType.Static

    def test_parses_relative(self):
        assert parse_position_type("relative") == yoga.PositionType.Relative

    def test_parses_absolute(self):
        assert parse_position_type("absolute") == yoga.PositionType.Absolute

    def test_handles_null(self):
        assert parse_position_type(None) == yoga.PositionType.Relative

    def test_handles_undefined(self):
        assert parse_position_type(None) == yoga.PositionType.Relative

    def test_handles_uppercase(self):
        assert parse_position_type("ABSOLUTE") == yoga.PositionType.Absolute

    def test_returns_default_for_invalid_value(self):
        assert parse_position_type("invalid") == yoga.PositionType.Static


class TestParseWrap:
    """parseWrap"""

    def test_parses_no_wrap(self):
        assert parse_wrap("no-wrap") == yoga.Wrap.NoWrap

    def test_parses_wrap(self):
        assert parse_wrap("wrap") == yoga.Wrap.Wrap

    def test_parses_wrap_reverse(self):
        assert parse_wrap("wrap-reverse") == yoga.Wrap.WrapReverse

    def test_handles_null(self):
        assert parse_wrap(None) == yoga.Wrap.NoWrap

    def test_handles_undefined(self):
        assert parse_wrap(None) == yoga.Wrap.NoWrap

    def test_handles_uppercase(self):
        assert parse_wrap("WRAP") == yoga.Wrap.Wrap

    def test_returns_default_for_invalid_value(self):
        assert parse_wrap("invalid") == yoga.Wrap.NoWrap
