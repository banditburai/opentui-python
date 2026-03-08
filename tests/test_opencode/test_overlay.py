"""Tests for overlay manager, fuzzy search, and dialog components."""

from __future__ import annotations

import pytest

from opentui.components import Box, Text

from opencode.tui.fuzzy import FuzzyMatch, fuzzy_filter, fuzzy_match
from opencode.tui.overlay import OverlayManager
from opencode.tui.components.dialog import (
    alert_dialog,
    confirm_dialog,
    dialog_box,
    help_dialog,
    prompt_dialog,
    select_dialog,
    select_item,
)
from opencode.tui.themes import init_theme


@pytest.fixture(autouse=True)
def _theme():
    init_theme("opencode", "dark")


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------


class TestFuzzyMatch:
    def test_exact_match(self):
        m = fuzzy_match("abc", "abc")
        assert m is not None
        assert m.positions == (0, 1, 2)

    def test_substring_match(self):
        m = fuzzy_match("ac", "abc")
        assert m is not None
        assert m.positions == (0, 2)

    def test_no_match(self):
        m = fuzzy_match("xyz", "abc")
        assert m is None

    def test_empty_query(self):
        m = fuzzy_match("", "abc")
        assert m is not None
        assert m.score == 0

    def test_case_insensitive(self):
        m = fuzzy_match("ABC", "abcdef")
        assert m is not None

    def test_word_start_bonus(self):
        m1 = fuzzy_match("c", "abc")
        m2 = fuzzy_match("c", "a-c")
        # "c" after "-" should score higher
        assert m2 is not None and m1 is not None
        assert m2.score >= m1.score

    def test_consecutive_bonus(self):
        m1 = fuzzy_match("ab", "axbx")
        m2 = fuzzy_match("ab", "abxx")
        assert m2 is not None and m1 is not None
        assert m2.score > m1.score

    def test_shorter_target_preferred(self):
        m1 = fuzzy_match("a", "a")
        m2 = fuzzy_match("a", "abcdefghijklmnop")
        assert m1 is not None and m2 is not None
        assert m1.score > m2.score


class TestFuzzyFilter:
    def test_filters_and_sorts(self):
        items = ["apple", "banana", "apricot", "cherry"]
        results = fuzzy_filter("ap", items)
        labels = [r[0] for r in results]
        assert "apple" in labels
        assert "apricot" in labels
        assert "cherry" not in labels

    def test_empty_query_returns_all(self):
        items = ["a", "b", "c"]
        results = fuzzy_filter("", items)
        assert len(results) == 3

    def test_no_matches(self):
        items = ["abc", "def"]
        results = fuzzy_filter("xyz", items)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Overlay manager
# ---------------------------------------------------------------------------


class TestOverlayManager:
    def test_initial_state(self):
        mgr = OverlayManager()
        assert mgr.count == 0
        assert not mgr.is_active
        assert mgr.peek() is None

    def test_push_pop(self):
        mgr = OverlayManager()
        fn1 = lambda: Box(Text("overlay1"))
        fn2 = lambda: Box(Text("overlay2"))

        mgr.push(fn1)
        assert mgr.count == 1
        assert mgr.is_active

        mgr.push(fn2)
        assert mgr.count == 2

        popped = mgr.pop()
        assert popped is fn2
        assert mgr.count == 1

        popped = mgr.pop()
        assert popped is fn1
        assert mgr.count == 0

    def test_pop_empty(self):
        mgr = OverlayManager()
        assert mgr.pop() is None

    def test_peek(self):
        mgr = OverlayManager()
        fn = lambda: Box(Text("test"))
        mgr.push(fn)
        assert mgr.peek() is fn
        assert mgr.count == 1  # peek doesn't remove

    def test_clear(self):
        mgr = OverlayManager()
        mgr.push(lambda: Box(Text("a")))
        mgr.push(lambda: Box(Text("b")))
        mgr.clear()
        assert mgr.count == 0

    def test_render_no_overlays(self):
        mgr = OverlayManager()
        base = Box(Text("base"))
        result = mgr.render(base)
        assert result is base  # unchanged

    def test_render_with_overlay(self):
        mgr = OverlayManager()
        base = Box(Text("base"))
        mgr.push(lambda: Box(Text("overlay")))
        result = mgr.render(base)
        assert isinstance(result, Box)
        assert result is not base  # wrapped


# ---------------------------------------------------------------------------
# Dialog components
# ---------------------------------------------------------------------------


class TestDialogs:
    def test_dialog_box(self):
        d = dialog_box(Text("content"), title="Test")
        assert isinstance(d, Box)

    def test_select_item(self):
        item = select_item(label="Option 1", selected=True)
        assert isinstance(item, Box)

    def test_select_dialog(self):
        items = [
            {"label": "Theme", "description": "Switch theme"},
            {"label": "Model", "description": "Switch model"},
        ]
        d = select_dialog(title="Commands", items=items)
        assert isinstance(d, Box)

    def test_select_dialog_with_query(self):
        items = [
            {"label": "Theme"},
            {"label": "Model"},
        ]
        d = select_dialog(title="Commands", items=items, query="th")
        assert isinstance(d, Box)

    def test_select_dialog_with_categories(self):
        items = [
            {"label": "Theme", "category": "Settings"},
            {"label": "Font", "category": "Settings"},
            {"label": "Run", "category": "Actions"},
        ]
        d = select_dialog(title="Commands", items=items)
        assert isinstance(d, Box)

    def test_alert_dialog(self):
        d = alert_dialog(title="Error", message="Something went wrong")
        assert isinstance(d, Box)

    def test_confirm_dialog(self):
        d = confirm_dialog(title="Confirm", message="Are you sure?")
        assert isinstance(d, Box)

    def test_prompt_dialog(self):
        d = prompt_dialog(title="Input", placeholder="Enter name...")
        assert isinstance(d, Box)

    def test_prompt_dialog_with_value(self):
        d = prompt_dialog(title="Input", value="hello")
        assert isinstance(d, Box)

    def test_help_dialog(self):
        bindings = [("Ctrl+K", "Command palette"), ("Ctrl+N", "New session")]
        d = help_dialog(bindings=bindings)
        assert isinstance(d, Box)
