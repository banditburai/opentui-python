"""Tests for SyntaxStyle — ported from syntax-style.test.ts (71 tests).

Upstream: reference/opentui/packages/core/src/syntax-style.test.ts
"""

from __future__ import annotations

import time

import pytest
from opentui.structs import RGBA
from opentui.editor.syntax_style import SyntaxStyle, StyleDefinition


@pytest.fixture
def style():
    s = SyntaxStyle.create()
    yield s
    s.destroy()


# ── create ──────────────────────────────────────────────────────────────


class TestCreate:
    def test_creates_new_instance(self):
        s = SyntaxStyle.create()
        assert s is not None
        assert s.get_style_count() == 0
        s.destroy()

    def test_creates_multiple_independent_instances(self):
        s1 = SyntaxStyle.create()
        s2 = SyntaxStyle.create()
        s1.register_style("test", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert s1.get_style_count() == 1
        assert s2.get_style_count() == 0
        s1.destroy()
        s2.destroy()


# ── registerStyle ───────────────────────────────────────────────────────


class TestRegisterStyle:
    def test_register_simple_style(self, style: SyntaxStyle):
        sid = style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert sid > 0
        assert style.get_style_count() == 1

    def test_register_fg_and_bg(self, style: SyntaxStyle):
        sid = style.register_style(
            "string", StyleDefinition(fg=RGBA(0, 1, 0, 1), bg=RGBA(0, 0, 0, 1))
        )
        assert sid > 0
        assert style.get_style_count() == 1

    def test_register_with_attributes(self, style: SyntaxStyle):
        sid = style.register_style("bold-keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1), bold=True))
        assert sid > 0
        assert style.get_style_count() == 1

    def test_register_multiple_attributes(self, style: SyntaxStyle):
        sid = style.register_style(
            "styled", StyleDefinition(fg=RGBA(1, 0, 0, 1), bold=True, italic=True, underline=True)
        )
        assert sid > 0
        assert style.get_style_count() == 1

    def test_register_multiple_different_styles(self, style: SyntaxStyle):
        id1 = style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        id2 = style.register_style("string", StyleDefinition(fg=RGBA(0, 1, 0, 1)))
        id3 = style.register_style("comment", StyleDefinition(fg=RGBA(0.5, 0.5, 0.5, 1)))
        assert id1 != id2
        assert id2 != id3
        assert id1 != id3
        assert style.get_style_count() == 3

    def test_same_name_returns_existing_id(self, style: SyntaxStyle):
        id1 = style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        id2 = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1)))
        assert id1 == id2
        assert style.get_style_count() == 1

    def test_empty_style(self, style: SyntaxStyle):
        sid = style.register_style("plain", StyleDefinition())
        assert sid > 0
        assert style.get_style_count() == 1

    def test_bg_only(self, style: SyntaxStyle):
        sid = style.register_style("highlighted", StyleDefinition(bg=RGBA(1, 1, 0, 1)))
        assert sid > 0
        assert style.get_style_count() == 1

    def test_attributes_only(self, style: SyntaxStyle):
        sid = style.register_style("bold-only", StyleDefinition(bold=True))
        assert sid > 0
        assert style.get_style_count() == 1

    def test_dim_attribute(self, style: SyntaxStyle):
        sid = style.register_style("dimmed", StyleDefinition(fg=RGBA(1, 1, 1, 1), dim=True))
        assert sid > 0
        assert style.get_style_count() == 1

    def test_special_chars_in_names(self, style: SyntaxStyle):
        id1 = style.register_style("keyword.control", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        id2 = style.register_style("variable.parameter", StyleDefinition(fg=RGBA(0, 1, 0, 1)))
        assert id1 > 0
        assert id2 > 0
        assert id1 != id2
        assert style.get_style_count() == 2

    def test_many_styles(self, style: SyntaxStyle):
        ids: list[int] = []
        for i in range(100):
            sid = style.register_style(f"style-{i}", StyleDefinition(fg=RGBA(i / 100, 0, 0, 1)))
            ids.append(sid)
        assert style.get_style_count() == 100
        assert len(set(ids)) == 100


# ── resolveStyleId ──────────────────────────────────────────────────────


class TestResolveStyleId:
    def test_resolve_registered(self, style: SyntaxStyle):
        reg_id = style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert style.resolve_style_id("keyword") == reg_id

    def test_unregistered_returns_none(self, style: SyntaxStyle):
        assert style.resolve_style_id("nonexistent") is None

    def test_resolve_multiple(self, style: SyntaxStyle):
        id1 = style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        id2 = style.register_style("string", StyleDefinition(fg=RGBA(0, 1, 0, 1)))
        assert style.resolve_style_id("keyword") == id1
        assert style.resolve_style_id("string") == id2

    def test_caches_resolved_ids(self, style: SyntaxStyle):
        reg_id = style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        r1 = style.resolve_style_id("keyword")
        r2 = style.resolve_style_id("keyword")
        assert r1 == reg_id
        assert r2 == reg_id

    def test_empty_string_name(self, style: SyntaxStyle):
        sid = style.register_style("", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert style.resolve_style_id("") == sid

    def test_case_sensitive(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert style.resolve_style_id("keyword") is not None
        assert style.resolve_style_id("Keyword") is None
        assert style.resolve_style_id("KEYWORD") is None


# ── getStyleId ──────────────────────────────────────────────────────────


class TestGetStyleId:
    def test_exact_match(self, style: SyntaxStyle):
        sid = style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert style.get_style_id("keyword") == sid

    def test_dotted_fallback(self, style: SyntaxStyle):
        base_id = style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert style.get_style_id("keyword.control") == base_id
        assert style.get_style_id("keyword.operator") == base_id

    def test_prefer_exact_over_base(self, style: SyntaxStyle):
        base_id = style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        specific_id = style.register_style("keyword.control", StyleDefinition(fg=RGBA(0, 1, 0, 1)))
        assert style.get_style_id("keyword") == base_id
        assert style.get_style_id("keyword.control") == specific_id
        assert style.get_style_id("keyword.operator") == base_id

    def test_nonexistent_returns_none(self, style: SyntaxStyle):
        assert style.get_style_id("nonexistent") is None
        assert style.get_style_id("nonexistent.scope") is None

    def test_multiple_dot_levels(self, style: SyntaxStyle):
        base_id = style.register_style("meta", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert style.get_style_id("meta.tag.xml") == base_id

    def test_no_dots(self, style: SyntaxStyle):
        sid = style.register_style("comment", StyleDefinition(fg=RGBA(0.5, 0.5, 0.5, 1)))
        assert style.get_style_id("comment") == sid


# ── getStyleCount ───────────────────────────────────────────────────────


class TestGetStyleCount:
    def test_empty(self, style: SyntaxStyle):
        assert style.get_style_count() == 0

    def test_after_registering(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert style.get_style_count() == 1
        style.register_style("string", StyleDefinition(fg=RGBA(0, 1, 0, 1)))
        assert style.get_style_count() == 2
        style.register_style("comment", StyleDefinition(fg=RGBA(0.5, 0.5, 0.5, 1)))
        assert style.get_style_count() == 3

    def test_no_increment_for_duplicates(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert style.get_style_count() == 1
        style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1)))
        assert style.get_style_count() == 1


# ── clearNameCache ──────────────────────────────────────────────────────


class TestClearNameCache:
    def test_clear_and_reresolve(self, style: SyntaxStyle):
        sid = style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        style.resolve_style_id("keyword")
        style.clear_name_cache()
        assert style.resolve_style_id("keyword") == sid

    def test_does_not_affect_styles(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        style.register_style("string", StyleDefinition(fg=RGBA(0, 1, 0, 1)))
        style.clear_name_cache()
        assert style.get_style_count() == 2


# ── ptr ─────────────────────────────────────────────────────────────────


class TestPtr:
    def test_returns_valid_pointer(self, style: SyntaxStyle):
        p = style.ptr
        assert p is not None

    def test_same_ptr_for_same_instance(self, style: SyntaxStyle):
        assert style.ptr is style.ptr

    def test_different_ptrs_for_different_instances(self, style: SyntaxStyle):
        s2 = SyntaxStyle.create()
        assert style.ptr is not s2.ptr
        s2.destroy()


# ── destroy ─────────────────────────────────────────────────────────────


class TestDestroy:
    def test_destroy_instance(self):
        s = SyntaxStyle.create()
        s.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        s.destroy()
        with pytest.raises(RuntimeError, match="NativeSyntaxStyle is destroyed"):
            s.get_style_count()

    def test_double_destroy_safe(self):
        s = SyntaxStyle.create()
        s.destroy()
        s.destroy()  # should not raise

    def test_methods_throw_after_destroy(self):
        s = SyntaxStyle.create()
        s.destroy()
        with pytest.raises(RuntimeError, match="NativeSyntaxStyle is destroyed"):
            s.register_style("test", StyleDefinition())
        with pytest.raises(RuntimeError, match="NativeSyntaxStyle is destroyed"):
            s.resolve_style_id("test")
        with pytest.raises(RuntimeError, match="NativeSyntaxStyle is destroyed"):
            s.get_style_id("test")
        with pytest.raises(RuntimeError, match="NativeSyntaxStyle is destroyed"):
            s.get_style_count()
        with pytest.raises(RuntimeError, match="NativeSyntaxStyle is destroyed"):
            _ = s.ptr


# ── fromStyles ──────────────────────────────────────────────────────────


class TestFromStyles:
    def test_create_from_styles(self):
        styles = {
            "keyword": StyleDefinition(fg=RGBA(1, 0, 0, 1), bold=True),
            "string": StyleDefinition(fg=RGBA(0, 1, 0, 1)),
            "comment": StyleDefinition(fg=RGBA(0.5, 0.5, 0.5, 1), italic=True),
        }
        s = SyntaxStyle.from_styles(styles)
        assert s.get_style_count() == 3
        assert s.resolve_style_id("keyword") is not None
        assert s.resolve_style_id("string") is not None
        assert s.resolve_style_id("comment") is not None
        s.destroy()

    def test_empty_styles(self):
        s = SyntaxStyle.from_styles({})
        assert s.get_style_count() == 0
        s.destroy()

    def test_preserves_style_defs(self):
        styles = {
            "keyword": StyleDefinition(fg=RGBA(1, 0, 0, 1), bold=True, italic=True),
        }
        s = SyntaxStyle.from_styles(styles)
        assert s.resolve_style_id("keyword") is not None
        s.destroy()


# ── fromTheme ───────────────────────────────────────────────────────────


class TestFromTheme:
    def test_create_from_theme(self):
        theme = [
            {
                "scope": ["keyword", "keyword.control"],
                "style": {"foreground": "#ff0000", "bold": True},
            },
            {"scope": ["string"], "style": {"foreground": "#00ff00"}},
        ]
        s = SyntaxStyle.from_theme(theme)
        assert s.get_style_count() == 3
        assert s.resolve_style_id("keyword") is not None
        assert s.resolve_style_id("keyword.control") is not None
        assert s.resolve_style_id("string") is not None
        s.destroy()

    def test_empty_theme(self):
        s = SyntaxStyle.from_theme([])
        assert s.get_style_count() == 0
        s.destroy()

    def test_multiple_scopes(self):
        theme = [
            {
                "scope": ["comment", "comment.line", "comment.block"],
                "style": {"foreground": "#808080", "italic": True},
            },
        ]
        s = SyntaxStyle.from_theme(theme)
        assert s.get_style_count() == 3
        assert s.resolve_style_id("comment") is not None
        assert s.resolve_style_id("comment.line") is not None
        assert s.resolve_style_id("comment.block") is not None
        s.destroy()

    def test_all_style_properties(self):
        theme = [
            {
                "scope": ["styled"],
                "style": {
                    "foreground": "#ff0000",
                    "background": "#000000",
                    "bold": True,
                    "italic": True,
                    "underline": True,
                    "dim": True,
                },
            },
        ]
        s = SyntaxStyle.from_theme(theme)
        assert s.get_style_count() == 1
        assert s.resolve_style_id("styled") is not None
        s.destroy()

    def test_rgb_color_format(self):
        theme = [
            {"scope": ["keyword"], "style": {"foreground": "rgb(255, 0, 0)"}},
        ]
        s = SyntaxStyle.from_theme(theme)
        assert s.resolve_style_id("keyword") is not None
        s.destroy()


# ── integration ─────────────────────────────────────────────────────────


class TestIntegration:
    def test_complex_scenario(self):
        theme = [
            {"scope": ["keyword"], "style": {"foreground": "#569cd6", "bold": True}},
            {"scope": ["string"], "style": {"foreground": "#ce9178"}},
            {"scope": ["comment"], "style": {"foreground": "#6a9955", "italic": True}},
            {"scope": ["variable"], "style": {"foreground": "#9cdcfe"}},
            {"scope": ["function"], "style": {"foreground": "#dcdcaa"}},
            {"scope": ["operator"], "style": {"foreground": "#d4d4d4"}},
        ]
        s = SyntaxStyle.from_theme(theme)
        assert s.get_style_count() == 6
        kid = s.get_style_id("keyword")
        sid = s.get_style_id("string")
        cid = s.get_style_id("comment")
        assert kid is not None
        assert sid is not None
        assert cid is not None
        assert kid != sid
        assert sid != cid
        s.destroy()

    def test_1000_styles_perf(self, style: SyntaxStyle):
        import random

        start = time.time()
        for i in range(1000):
            style.register_style(
                f"style-{i}",
                StyleDefinition(fg=RGBA(random.random(), random.random(), random.random(), 1)),
            )
        register_time = time.time() - start

        resolve_start = time.time()
        for i in range(1000):
            style.resolve_style_id(f"style-{i}")
        resolve_time = time.time() - resolve_start

        assert register_time < 1.0
        assert resolve_time < 0.1
        assert style.get_style_count() == 1000

    def test_name_collision(self, style: SyntaxStyle):
        id1 = style.register_style("test", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        id2 = style.register_style("test", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        assert id1 == id2
        assert style.get_style_count() == 1

    def test_maintain_registry_across_cache_clears(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        style.register_style("string", StyleDefinition(fg=RGBA(0, 1, 0, 1)))
        style.register_style("comment", StyleDefinition(fg=RGBA(0.5, 0.5, 0.5, 1)))
        c1 = style.get_style_count()
        style.clear_name_cache()
        c2 = style.get_style_count()
        assert c1 == c2 == 3


# ── edge cases ──────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_very_long_name(self, style: SyntaxStyle):
        long_name = "a" * 1000
        sid = style.register_style(long_name, StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert sid > 0
        assert style.resolve_style_id(long_name) == sid

    def test_unicode_name(self, style: SyntaxStyle):
        sid = style.register_style("关键字", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert sid > 0
        assert style.resolve_style_id("关键字") == sid

    def test_special_character_names(self, style: SyntaxStyle):
        names = [
            "style-with-dashes",
            "style_with_underscores",
            "style.with.dots",
            "style:with:colons",
            "style/with/slashes",
        ]
        for name in names:
            sid = style.register_style(name, StyleDefinition(fg=RGBA(1, 0, 0, 1)))
            assert sid > 0
            assert style.resolve_style_id(name) == sid

    def test_full_alpha_range(self, style: SyntaxStyle):
        id1 = style.register_style("transparent", StyleDefinition(fg=RGBA(1, 0, 0, 0)))
        id2 = style.register_style("semi-transparent", StyleDefinition(fg=RGBA(1, 0, 0, 0.5)))
        id3 = style.register_style("opaque", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert id1 > 0
        assert id2 > 0
        assert id3 > 0

    def test_all_attribute_combinations(self, style: SyntaxStyle):
        combos = [
            {"bold": True},
            {"italic": True},
            {"underline": True},
            {"dim": True},
            {"bold": True, "italic": True},
            {"bold": True, "underline": True},
            {"bold": True, "dim": True},
            {"italic": True, "underline": True},
            {"italic": True, "dim": True},
            {"underline": True, "dim": True},
            {"bold": True, "italic": True, "underline": True},
            {"bold": True, "italic": True, "dim": True},
            {"bold": True, "underline": True, "dim": True},
            {"italic": True, "underline": True, "dim": True},
            {"bold": True, "italic": True, "underline": True, "dim": True},
        ]
        for i, combo in enumerate(combos):
            sid = style.register_style(f"combo-{i}", StyleDefinition(fg=RGBA(1, 0, 0, 1), **combo))
            assert sid > 0
        assert style.get_style_count() == len(combos)


# ── getStyle ────────────────────────────────────────────────────────────


class TestGetStyle:
    def test_retrieve_registered(self, style: SyntaxStyle):
        sdef = StyleDefinition(fg=RGBA(1, 0, 0, 1), bold=True)
        style.register_style("keyword", sdef)
        retrieved = style.get_style("keyword")
        assert retrieved is not None
        assert retrieved.fg == sdef.fg
        assert retrieved.bold is True

    def test_unregistered_returns_none(self, style: SyntaxStyle):
        assert style.get_style("nonexistent") is None

    def test_dotted_fallback(self, style: SyntaxStyle):
        base = StyleDefinition(fg=RGBA(1, 0, 0, 1), bold=True)
        style.register_style("keyword", base)
        retrieved = style.get_style("keyword.control")
        assert retrieved is not None
        assert retrieved.fg == base.fg
        assert retrieved.bold is True

    def test_prefer_exact_match(self, style: SyntaxStyle):
        base = StyleDefinition(fg=RGBA(1, 0, 0, 1))
        specific = StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True)
        style.register_style("keyword", base)
        style.register_style("keyword.control", specific)
        exact = style.get_style("keyword.control")
        assert exact is not None and exact.fg == specific.fg and exact.bold is True
        fallback = style.get_style("keyword.operator")
        assert fallback is not None and fallback.fg == base.fg

    def test_no_prototype_leaks(self, style: SyntaxStyle):
        assert style.get_style("constructor") is None
        assert style.get_style("toString") is None
        assert style.get_style("hasOwnProperty") is None

    def test_style_named_constructor(self, style: SyntaxStyle):
        cdef = StyleDefinition(fg=RGBA(1, 0.5, 0, 1), bold=True)
        style.register_style("constructor", cdef)
        retrieved = style.get_style("constructor")
        assert retrieved is not None
        assert retrieved.fg == cdef.fg
        assert retrieved.bold is True

    def test_multiple_dot_levels(self, style: SyntaxStyle):
        base = StyleDefinition(fg=RGBA(1, 0, 0, 1))
        style.register_style("meta", base)
        retrieved = style.get_style("meta.tag.xml")
        assert retrieved is not None
        assert retrieved.fg == base.fg


# ── mergeStyles ─────────────────────────────────────────────────────────


class TestMergeStyles:
    def test_single_style(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1), bold=True))
        merged = style.merge_styles("keyword")
        assert merged.fg == RGBA(1, 0, 0, 1)
        assert merged.attributes > 0

    def test_multiple_precedence(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1), bold=True))
        style.register_style("emphasis", StyleDefinition(italic=True))
        style.register_style("override", StyleDefinition(fg=RGBA(0, 1, 0, 1)))
        merged = style.merge_styles("keyword", "emphasis", "override")
        assert merged.fg == RGBA(0, 1, 0, 1)
        assert merged.attributes > 0

    def test_dotted_fallback(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1), bold=True))
        merged = style.merge_styles("keyword.operator")
        assert merged.fg == RGBA(1, 0, 0, 1)
        assert merged.attributes > 0

    def test_nonexistent_returns_empty(self, style: SyntaxStyle):
        merged = style.merge_styles("nonexistent")
        assert merged.fg is None
        assert merged.bg is None
        assert merged.attributes == 0

    def test_cache(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        assert style.get_cache_size() == 0
        r1 = style.merge_styles("keyword.operator")
        assert style.get_cache_size() == 1
        r2 = style.merge_styles("keyword.operator")
        assert style.get_cache_size() == 1
        assert r1 is r2

    def test_all_attributes(self, style: SyntaxStyle):
        style.register_style(
            "complex",
            StyleDefinition(
                fg=RGBA(1, 0, 0, 1),
                bg=RGBA(0.2, 0.2, 0.2, 1),
                bold=True,
                italic=True,
                underline=True,
                dim=True,
            ),
        )
        merged = style.merge_styles("complex")
        assert merged.fg == RGBA(1, 0, 0, 1)
        assert merged.bg == RGBA(0.2, 0.2, 0.2, 1)
        assert merged.attributes > 0

    def test_empty_names(self, style: SyntaxStyle):
        merged = style.merge_styles()
        assert merged.fg is None
        assert merged.bg is None
        assert merged.attributes == 0


# ── clearCache / getCacheSize ───────────────────────────────────────────


class TestCacheOps:
    def test_clear_cache(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        style.merge_styles("keyword")
        style.merge_styles("keyword.operator")
        assert style.get_cache_size() == 2
        style.clear_cache()
        assert style.get_cache_size() == 0

    def test_clear_does_not_affect_styles(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        style.merge_styles("keyword")
        style.clear_cache()
        assert style.get_style_count() == 1
        assert style.resolve_style_id("keyword") is not None

    def test_remerge_after_clear(self, style: SyntaxStyle):
        style.register_style("keyword", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        r1 = style.merge_styles("keyword")
        style.clear_cache()
        r2 = style.merge_styles("keyword")
        assert r1.fg == r2.fg
        assert r1.attributes == r2.attributes
