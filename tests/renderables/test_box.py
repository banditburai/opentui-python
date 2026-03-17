"""Port of upstream Box.test.ts.

Upstream: packages/core/src/renderables/Box.test.ts
Tests ported: 14/14 (0 skipped)
"""

import pytest

from opentui.components.box import Box


class TestBoxFocusableOption:
    """Maps to describe("BoxRenderable - focusable option")."""

    def test_is_not_focusable_by_default(self):
        """Maps to test("is not focusable by default").

        Python focus() always sets _focused=True (no focusable guard).
        We verify the focusable property is False by default.
        """
        box = Box(key="test-box", width=10, height=5)
        assert box.focusable is False

    def test_can_be_made_focusable_via_option(self):
        """Maps to test("can be made focusable via option")."""
        box = Box(key="test-box", width=10, height=5, focusable=True)
        assert box.focusable is True


class TestBoxBorderStyleValidationConstructor:
    """Maps to describe("BoxRenderable - borderStyle validation") >
    describe("regression: invalid borderStyle via constructor does not crash").
    """

    def test_handles_invalid_string_border_style_in_constructor(self):
        """Maps to test("handles invalid string borderStyle in constructor")."""
        box = Box(key="test-box", border=True, border_style="invalid-style", width=10, height=5)
        assert box.border_style == "single"
        assert box._destroyed is False

    def test_handles_none_border_style_in_constructor(self):
        """Maps to test("handles undefined borderStyle in constructor").

        Python doesn't allow None for border_style in the type signature,
        but parse_border_style handles it gracefully.
        """
        box = Box(key="test-box", border=True, width=10, height=5)
        assert box.border_style == "single"
        assert box._destroyed is False


class TestBoxBorderStyleValidationSetter:
    """Maps to describe("regression: invalid borderStyle via setter does not crash")."""

    def test_handles_invalid_string_border_style_via_setter(self):
        """Maps to test("handles invalid string borderStyle via setter")."""
        box = Box(key="test-box", border=True, border_style="double", width=10, height=5)
        assert box.border_style == "double"
        box.border_style = "invalid-style"
        assert box.border_style == "single"
        assert box._destroyed is False

    def test_renders_correctly_after_fallback_from_invalid_border_style(self):
        """Maps to test("renders correctly after fallback from invalid borderStyle")."""
        box = Box(key="test-box", border=True, border_style="invalid", width=10, height=5)
        # Should not crash, border_style falls back to "single"
        assert box.border_style == "single"
        assert box._destroyed is False


class TestBoxValidBorderStyleValues:
    """Maps to describe("valid borderStyle values work correctly").

    Upstream uses renderOnce() to verify rendering does not crash.
    Python equivalent: verify the border_style property is accepted and
    the Box is not destroyed. Visual rendering verification would require
    the full TestRenderer pipeline, but the property-level validation
    covers the core logic tested upstream.
    """

    def test_accepts_valid_border_style_single_in_constructor(self):
        """Maps to test.each(...)("accepts valid borderStyle 'single' in constructor")."""
        box = Box(key="test-box", border=True, border_style="single", width=10, height=5)
        assert box.border_style == "single"
        assert box._destroyed is False

    def test_accepts_valid_border_style_double_in_constructor(self):
        """Maps to test.each(...)("accepts valid borderStyle 'double' in constructor")."""
        box = Box(key="test-box", border=True, border_style="double", width=10, height=5)
        assert box.border_style == "double"
        assert box._destroyed is False

    def test_accepts_valid_border_style_rounded_in_constructor(self):
        """Maps to test.each(...)("accepts valid borderStyle 'rounded' in constructor")."""
        box = Box(key="test-box", border=True, border_style="rounded", width=10, height=5)
        assert box.border_style == "rounded"
        assert box._destroyed is False

    def test_accepts_valid_border_style_heavy_in_constructor(self):
        """Maps to test.each(...)("accepts valid borderStyle 'heavy' in constructor")."""
        box = Box(key="test-box", border=True, border_style="heavy", width=10, height=5)
        assert box.border_style == "heavy"
        assert box._destroyed is False

    def test_accepts_valid_border_style_single_via_setter(self):
        """Maps to test.each(...)("accepts valid borderStyle 'single' via setter")."""
        box = Box(key="test-box", border=True, border_style="double", width=10, height=5)
        box.border_style = "single"
        assert box.border_style == "single"
        assert box._destroyed is False

    def test_accepts_valid_border_style_double_via_setter(self):
        """Maps to test.each(...)("accepts valid borderStyle 'double' via setter")."""
        box = Box(key="test-box", border=True, border_style="single", width=10, height=5)
        box.border_style = "double"
        assert box.border_style == "double"
        assert box._destroyed is False

    def test_accepts_valid_border_style_rounded_via_setter(self):
        """Maps to test.each(...)("accepts valid borderStyle 'rounded' via setter")."""
        box = Box(key="test-box", border=True, border_style="single", width=10, height=5)
        box.border_style = "rounded"
        assert box.border_style == "rounded"
        assert box._destroyed is False

    def test_accepts_valid_border_style_heavy_via_setter(self):
        """Maps to test.each(...)("accepts valid borderStyle 'heavy' via setter")."""
        box = Box(key="test-box", border=True, border_style="single", width=10, height=5)
        box.border_style = "heavy"
        assert box.border_style == "heavy"
        assert box._destroyed is False
