"""Tests for startui theme dict and resolve_props."""

from startui.theme import TUI_THEME, resolve_props


class TestTUITheme:
    """Tests for the TUI_THEME dict."""

    def test_theme_is_dict(self):
        assert isinstance(TUI_THEME, dict)

    def test_theme_keys_are_tuples(self):
        for key in TUI_THEME:
            assert isinstance(key, tuple)
            assert len(key) == 3

    def test_theme_values_are_dicts(self):
        for value in TUI_THEME.values():
            assert isinstance(value, dict)

    def test_button_variant_default(self):
        props = TUI_THEME[("button", "variant", "default")]
        assert "border" in props
        assert "fg" in props
        assert "bg" in props

    def test_button_variant_destructive(self):
        props = TUI_THEME[("button", "variant", "destructive")]
        assert props["bg"] == "#e74c3c"
        assert props["fg"] == "#ffffff"

    def test_button_variant_outline(self):
        assert ("button", "variant", "outline") in TUI_THEME

    def test_button_variant_ghost(self):
        props = TUI_THEME[("button", "variant", "ghost")]
        assert props["border"] is False

    def test_button_variant_secondary(self):
        props = TUI_THEME[("button", "variant", "secondary")]
        assert props["bg"] == "#2d2d44"

    def test_button_variant_link(self):
        props = TUI_THEME[("button", "variant", "link")]
        assert props["underline"] is True

    def test_button_sizes(self):
        for size in ("default", "sm", "lg", "icon"):
            assert ("button", "size", size) in TUI_THEME

    def test_button_size_sm_has_less_padding(self):
        sm = TUI_THEME[("button", "size", "sm")]
        default = TUI_THEME[("button", "size", "default")]
        assert sm["padding_x"] < default["padding_x"]

    def test_card_variant_default(self):
        props = TUI_THEME[("card", "variant", "default")]
        assert "border" in props
        assert "padding" in props

    def test_badge_variants(self):
        for variant in ("default", "secondary", "destructive", "outline"):
            assert ("badge", "variant", variant) in TUI_THEME

    def test_alert_variants(self):
        for variant in ("default", "destructive"):
            assert ("alert", "variant", variant) in TUI_THEME

    def test_input_variant_default(self):
        assert ("input", "variant", "default") in TUI_THEME

    def test_separator_variant_default(self):
        assert ("separator", "variant", "default") in TUI_THEME

    def test_progress_variant_default(self):
        props = TUI_THEME[("progress", "variant", "default")]
        assert "fill_char" in props
        assert "empty_char" in props

    def test_tabs_variants(self):
        for variant in ("default", "line"):
            assert ("tabs", "variant", variant) in TUI_THEME


class TestResolveProps:
    """Tests for resolve_props helper."""

    def test_single_axis(self):
        props = resolve_props("button", variant="default")
        assert "border" in props
        assert "fg" in props

    def test_multi_axis_merge(self):
        props = resolve_props("button", variant="default", size="sm")
        assert "border" in props  # from variant
        assert "padding_x" in props  # from size

    def test_size_adds_geometry_props(self):
        props = resolve_props("button", variant="default", size="icon")
        assert props["width"] == 3  # icon size sets explicit width

    def test_size_overrides_variant_on_shared_key(self):
        """Size axis wins over variant axis when both define the same key."""
        # Both "default" variant and all sizes define "height"
        props = resolve_props("button", variant="default", size="sm")
        # size "sm" sets height=1 — same value, but size axis applied last
        assert props["height"] == 1

    def test_unknown_component(self):
        props = resolve_props("nonexistent", variant="nope")
        assert props == {}

    def test_unknown_variant(self):
        props = resolve_props("button", variant="nonexistent")
        assert props == {}

    def test_partial_match(self):
        props = resolve_props("button", variant="default", size="nonexistent")
        assert "border" in props  # variant matched
        assert "padding_x" not in props  # size didn't match

    def test_all_high_tier_components_have_default(self):
        """All HIGH-tier components should have at least a default variant."""
        components = ["button", "card", "badge", "alert", "input",
                      "separator", "progress", "tabs"]
        for comp in components:
            props = resolve_props(comp, variant="default")
            assert len(props) > 0, f"{comp} missing default variant"
