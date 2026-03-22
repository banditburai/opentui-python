"""Port of upstream yoga.options.test.ts.

Upstream: packages/core/src/lib/yoga.options.test.ts
"""

import yoga

from opentui.layout import (
    parse_align,
    parse_align_items,
    parse_display,
    parse_flex_direction,
    parse_justify,
    parse_overflow,
    parse_position_type,
    parse_wrap,
)


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
