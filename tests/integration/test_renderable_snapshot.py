"""Port of upstream renderable.snapshot.test.ts.

Upstream: packages/core/src/tests/renderable.snapshot.test.ts
Tests ported: 19/19 (0 skipped)
"""

import pytest

from opentui import create_test_renderer
from opentui.components.base import BaseRenderable, Renderable
from opentui.components.box import Box
from opentui.components.text_renderable import TextRenderable


class TestRenderableInsertBefore:
    """Renderable - insertBefore"""

    async def test_reproduces_insert_before_behavior_with_state_change_after_timeout(self):
        """Reproduces insertBefore behavior where a child is moved after an initial render.

        Upstream uses setTimeout(100) to simulate a delayed state change; here we
        simply render a frame, call insertBefore, then render again and check the
        resulting child order and rendered output.

        Maps to test("reproduces insertBefore behavior with state change after timeout").
        """
        from opentui.native import is_available

        if not is_available():
            pytest.skip("Native bindings not available")

        setup = await create_test_renderer(width=10, height=5)

        container = Box(id="container", width=10, height=5)
        banana_text = TextRenderable(id="banana", content="banana")
        apple_text = TextRenderable(id="apple", content="apple")
        pear_text = TextRenderable(id="pear", content="pear")
        separator = Box(id="separator", width=20, height=1)

        container.add(banana_text)
        container.add(apple_text)
        container.add(pear_text)
        container.add(separator)

        setup.renderer.root.add(container)
        setup.render_frame()

        # Verify initial order: banana, apple, pear, separator
        children = container.get_children()
        assert len(children) == 4
        assert children[0].id == "banana"
        assert children[1].id == "apple"
        assert children[2].id == "pear"
        assert children[3].id == "separator"

        # Capture initial frame — all three text labels must be visible
        initial_frame = setup.capture_char_frame()
        assert "banana" in initial_frame
        assert "apple" in initial_frame
        assert "pear" in initial_frame

        # Simulate the delayed state change: move apple before separator
        # (in TS this happens after setTimeout(100))
        container.insert_before(apple_text, separator)
        setup.render_frame()

        # Verify reordered structure: banana, pear, apple, separator
        children_after = container.get_children()
        assert len(children_after) == 4
        assert children_after[0].id == "banana"
        assert children_after[1].id == "pear"
        assert children_after[2].id == "apple"
        assert children_after[3].id == "separator"

        # Capture reordered frame — all labels still present
        reordered_frame = setup.capture_char_frame()
        assert "banana" in reordered_frame
        assert "apple" in reordered_frame
        assert "pear" in reordered_frame

        setup.destroy()

    def test_ensure_add_with_index_works_correctly(self):
        """add(child, index) inserts at the given position."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        c = Renderable(id="C")
        parent.add(a)
        parent.add(c)
        # Insert B at index 1 (between A and C)
        idx = parent.add(b, index=1)
        assert idx == 1
        children = parent.get_children()
        assert [c.id for c in children] == ["A", "B", "C"]


class TestRenderableAddMethod:
    """Renderable - add method"""

    def test_basic_add_appends_to_end(self):
        """add() without index appends to the end."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        c = Renderable(id="C")
        parent.add(a)
        parent.add(b)
        parent.add(c)
        children = parent.get_children()
        assert [c.id for c in children] == ["A", "B", "C"]

    def test_add_with_index_0_inserts_at_beginning(self):
        """add(child, 0) places the child first."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        parent.add(a)
        parent.add(b, index=0)
        children = parent.get_children()
        assert [c.id for c in children] == ["B", "A"]

    def test_add_with_middle_index_inserts_correctly(self):
        """add(child, 1) inserts in the middle."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        c = Renderable(id="C")
        parent.add(a)
        parent.add(c)
        parent.add(b, index=1)
        children = parent.get_children()
        assert [c.id for c in children] == ["A", "B", "C"]

    def test_add_with_large_index_appends_to_end(self):
        """add(child, 999) with index beyond length appends to end."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        parent.add(a)
        parent.add(b, index=999)
        children = parent.get_children()
        assert len(children) == 2
        assert children[-1].id == "B"

    def test_add_returns_correct_index(self):
        """add() returns the insertion index."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        c = Renderable(id="C")
        assert parent.add(a) == 0
        assert parent.add(b) == 1
        assert parent.add(c) == 2
        # Add at beginning
        d = Renderable(id="D")
        assert parent.add(d, index=0) == 0

    def test_add_null_undefined_returns_negative_1(self):
        """add(None) returns -1."""
        parent = Renderable(id="parent")
        assert parent.add(None) == -1
        assert parent.get_children_count() == 0

    def test_re_adding_existing_child_moves_it(self):
        """Re-adding a child that's already present moves it to the new position."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        c = Renderable(id="C")
        parent.add(a)
        parent.add(b)
        parent.add(c)
        # Move A to the end
        parent.add(a)
        children = parent.get_children()
        assert [c.id for c in children] == ["B", "C", "A"]

    def test_adding_child_from_another_parent_removes_it_from_old_parent(self):
        """Adding a child that belongs to another parent removes it from the old parent."""
        parent1 = Renderable(id="parent1")
        parent2 = Renderable(id="parent2")
        child = Renderable(id="child")
        parent1.add(child)
        assert parent1.get_children_count() == 1
        parent2.add(child)
        assert parent1.get_children_count() == 0
        assert parent2.get_children_count() == 1
        assert parent2.get_renderable("child") is child


class TestRenderableInsertBeforeMethod:
    """Renderable - insertBefore method"""

    def test_insert_before_with_null_anchor_appends_to_end(self):
        """insertBefore(child, None) appends to end."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        parent.add(a)
        idx = parent.insert_before(b, None)
        children = parent.get_children()
        assert [c.id for c in children] == ["A", "B"]
        assert idx == 1

    def test_insert_before_inserts_at_correct_position(self):
        """insertBefore inserts child directly before the anchor."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        c = Renderable(id="C")
        parent.add(a)
        parent.add(c)
        parent.insert_before(b, c)
        children = parent.get_children()
        assert [c.id for c in children] == ["A", "B", "C"]

    def test_insert_before_at_beginning(self):
        """insertBefore with first child as anchor inserts at beginning."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        parent.add(a)
        parent.insert_before(b, a)
        children = parent.get_children()
        assert [c.id for c in children] == ["B", "A"]

    def test_insert_before_moves_existing_child(self):
        """insertBefore on an existing child moves it before the anchor."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        c = Renderable(id="C")
        parent.add(a)
        parent.add(b)
        parent.add(c)
        # Move C before A
        parent.insert_before(c, a)
        children = parent.get_children()
        assert [c.id for c in children] == ["C", "A", "B"]

    def test_insert_before_with_invalid_anchor_returns_negative_1(self):
        """insertBefore with anchor not in children returns -1."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        not_a_child = Renderable(id="phantom")
        parent.add(a)
        idx = parent.insert_before(b, not_a_child)
        assert idx == -1
        assert parent.get_children_count() == 1

    def test_insert_before_returns_correct_index(self):
        """insertBefore returns the index where the child was inserted."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        c = Renderable(id="C")
        parent.add(a)
        parent.add(c)
        idx = parent.insert_before(b, c)
        assert idx == 1

    def test_insert_before_with_null_object_returns_negative_1(self):
        """insertBefore(None, anchor) returns -1."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        parent.add(a)
        idx = parent.insert_before(None, a)
        assert idx == -1
        assert parent.get_children_count() == 1

    def test_complex_reordering_scenario(self):
        """Multiple insertBefore operations reorder children correctly."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        c = Renderable(id="C")
        d = Renderable(id="D")
        parent.add(a)
        parent.add(b)
        parent.add(c)
        parent.add(d)
        # Order: A, B, C, D
        # Move D before A
        parent.insert_before(d, a)
        assert [c.id for c in parent.get_children()] == ["D", "A", "B", "C"]
        # Move C before D
        parent.insert_before(c, d)
        assert [c.id for c in parent.get_children()] == ["C", "D", "A", "B"]
        # Move A before C
        parent.insert_before(a, c)
        assert [c.id for c in parent.get_children()] == ["A", "C", "D", "B"]

    def test_multiple_sequential_adds_and_inserts(self):
        """Mix of add and insertBefore operations works correctly."""
        parent = Renderable(id="parent")
        a = Renderable(id="A")
        b = Renderable(id="B")
        c = Renderable(id="C")
        d = Renderable(id="D")
        e = Renderable(id="E")
        parent.add(a)
        parent.add(c)
        parent.insert_before(b, c)
        assert [c.id for c in parent.get_children()] == ["A", "B", "C"]
        parent.add(e)
        parent.insert_before(d, e)
        assert [c.id for c in parent.get_children()] == ["A", "B", "C", "D", "E"]
        # Move B to end via add
        parent.add(b)
        assert [c.id for c in parent.get_children()] == ["A", "C", "D", "E", "B"]
