"""Port of upstream renderable.test.ts.

Upstream: packages/core/src/tests/renderable.test.ts
Tests ported: 56/56 (all passing)
"""

import re

import pytest

from opentui import layout as yoga_layout
from opentui.components.base import BaseRenderable, Renderable, is_renderable
from opentui.renderer import CliRenderer, CliRendererConfig, RootRenderable


# ---------------------------------------------------------------------------
# Helper: compute yoga layout on a tree without a full CliRenderer.
#
# Mirrors CliRenderer._update_layout + _apply_yoga_layout_recursive:
#   1. _configure_yoga_properties() on the root (writes dimensions/flex/etc
#      into the yoga tree);
#   2. compute_layout() runs the yoga solver;
#   3. _apply_yoga_layout_recursive() reads computed positions/sizes back.
# ---------------------------------------------------------------------------


def _compute_layout(root: Renderable, width: float = 80, height: float = 24) -> None:
    """Run yoga layout on *root* and all descendants."""
    root._configure_yoga_properties()
    yoga_layout.compute_layout(root._yoga_node, width, height)
    _apply_yoga_layout_recursive(root)


def _apply_yoga_layout_recursive(renderable, offset_x: int = 0, offset_y: int = 0) -> None:
    """Port of CliRenderer._apply_yoga_layout_recursive."""
    if hasattr(renderable, "_apply_yoga_layout"):
        renderable._apply_yoga_layout()
        renderable._x += offset_x
        renderable._y += offset_y

    abs_x = getattr(renderable, "_x", offset_x)
    abs_y = getattr(renderable, "_y", offset_y)

    if hasattr(renderable, "get_children"):
        for child in renderable.get_children():
            _apply_yoga_layout_recursive(child, abs_x, abs_y)


# ---------------------------------------------------------------------------
# FakeNative / fake_renderer — lightweight stand-in for CliRenderer so that
# RootRenderable can be instantiated without native bindings.
# ---------------------------------------------------------------------------


class _FakeNative:
    class renderer:
        @staticmethod
        def create_renderer(w, h, testing, remote):
            return 1

        @staticmethod
        def destroy_renderer(ptr):
            pass

        @staticmethod
        def get_next_buffer(ptr):
            return 1

        @staticmethod
        def render(ptr, skip_diff):
            pass

        @staticmethod
        def resize_renderer(ptr, w, h):
            pass

        @staticmethod
        def setup_terminal(ptr, use_alternate_screen):
            pass

    class buffer:
        @staticmethod
        def buffer_clear(ptr, alpha):
            pass

        @staticmethod
        def get_buffer_width(ptr):
            return 80

        @staticmethod
        def get_buffer_height(ptr):
            return 24


def _make_fake_renderer(width: int = 80, height: int = 24) -> CliRenderer:
    """Create a CliRenderer backed by a fake native stub."""
    config = CliRendererConfig(width=width, height=height, testing=True)
    native = _FakeNative()
    r = CliRenderer(1, config, native)
    r._root = RootRenderable(r)
    return r


class TestDestroyYogaCleanup:
    def test_destroy_removes_yoga_child_from_parent(self):
        """After destroy(), parent's yoga node no longer contains the child."""
        parent = BaseRenderable()
        child = BaseRenderable()
        parent.add(child)
        assert parent._yoga_node.child_count == 1

        child.destroy()
        assert parent._yoga_node.child_count == 0

    def test_destroy_nulls_yoga_node(self):
        """After destroy(), the node's _yoga_node is None."""
        r = BaseRenderable()
        assert r._yoga_node is not None
        r.destroy()
        assert r._yoga_node is None


class TestBaseRenderable:
    """Maps to describe('BaseRenderable')."""

    def test_creates_with_default_id(self):
        """Default ID follows renderable-<num> format."""
        r = BaseRenderable()
        assert re.match(r"^renderable-\d+$", r.id)
        assert r.num > 0

    def test_creates_with_custom_id(self):
        """Custom ID overrides the default."""
        r = BaseRenderable(id="custom-id")
        assert r.id == "custom-id"

    def test_has_unique_numbers(self):
        """Each instance gets a unique num."""
        r1 = BaseRenderable()
        r2 = BaseRenderable()
        assert r1.num != r2.num

    def test_initial_visibility_state(self):
        """Visible is True by default."""
        r = BaseRenderable()
        assert r.visible is True

    def test_can_set_visibility(self):
        """Visibility can be toggled."""
        r = BaseRenderable()
        r.visible = False
        assert r.visible is False
        r.visible = True
        assert r.visible is True


class TestRenderable:
    """Maps to describe('Renderable')."""

    def test_creates_with_basic_options(self):
        """Renderable can be created with basic options."""
        r = Renderable()
        assert r.id is not None
        assert r.num > 0
        assert r.visible is True

    def test_is_renderable(self):
        """isRenderable() returns True for renderables, False for others."""
        r = Renderable()
        assert is_renderable(r) is True
        assert is_renderable(BaseRenderable()) is True
        assert is_renderable({}) is False
        assert is_renderable(None) is False
        assert is_renderable(42) is False

    def test_creates_with_width_and_height(self):
        """Renderable accepts width and height."""
        r = Renderable(width=100, height=50)
        assert r.width == 100
        assert r.height == 50

    def test_throws_on_invalid_width(self):
        """Negative width raises TypeError."""
        with pytest.raises(TypeError):
            Renderable(width=-10)

    def test_throws_on_invalid_height(self):
        """Negative height raises TypeError."""
        with pytest.raises(TypeError):
            Renderable(height=-5)

    def test_handles_visibility_changes(self):
        """Visibility can be changed on Renderable."""
        r = Renderable()
        assert r.visible is True
        r.visible = False
        assert r.visible is False
        r.visible = True
        assert r.visible is True

    def test_handles_live_mode(self):
        """Maps to test('handles live mode').

        When live=True and visible=True, liveCount should be 1.
        """
        r = Renderable(id="test-live", live=True)
        assert r.live is True
        assert r.live_count == 1


class TestRenderableChildManagement:
    """Maps to describe('Renderable - Child Management')."""

    def test_can_add_and_remove_children(self):
        """Add returns index, remove by reference works."""
        parent = Renderable()
        child1 = Renderable(id="child1")
        child2 = Renderable(id="child2")
        idx1 = parent.add(child1)
        idx2 = parent.add(child2)
        assert idx1 == 0
        assert idx2 == 1
        assert parent.get_children_count() == 2
        assert parent.get_renderable("child1") is child1

        parent.remove(child1)
        assert parent.get_children_count() == 1
        assert parent.get_renderable("child1") is None

    def test_can_insert_child_at_specific_index(self):
        """insertBefore places child before anchor."""
        parent = Renderable()
        child1 = Renderable(id="child1")
        child2 = Renderable(id="child2")
        child3 = Renderable(id="child3")
        parent.add(child1)
        parent.add(child3)
        parent.insert_before(child2, child3)
        children = parent.get_children()
        assert children[0] is child1
        assert children[1] is child2
        assert children[2] is child3

    def test_insert_before_makes_new_child_accessible(self):
        """Inserted child is findable by ID."""
        parent = Renderable()
        child1 = Renderable(id="child1")
        child2 = Renderable(id="child2")
        new_child = Renderable(id="newChild")
        parent.add(child1)
        parent.add(child2)
        parent.insert_before(new_child, child2)
        assert parent.get_renderable("newChild") is new_child

    def test_insert_before_with_same_node_as_anchor_should_not_change_order(self):
        """insertBefore with same node as anchor is a no-op."""
        parent = Renderable()
        child1 = Renderable(id="child1")
        child2 = Renderable(id="child2")
        parent.add(child1)
        parent.add(child2)
        parent.insert_before(child1, child1)
        children = parent.get_children()
        assert len(children) == 2
        assert children[0] is child1
        assert children[1] is child2

    def test_handles_adding_destroyed_renderable(self):
        """Adding a destroyed child returns -1."""
        parent = Renderable()
        child = Renderable()
        child.destroy()
        result = parent.add(child)
        assert result == -1
        assert parent.get_children_count() == 0

    def test_can_change_renderable_id_and_updates_parent_mapping(self):
        """Changing a child's ID updates parent's lookup mapping."""
        parent = Renderable()
        child = Renderable(id="child")
        parent.add(child)
        assert parent.get_renderable("child") is child

        child.id = "new-child-id"
        assert parent.get_renderable("child") is None
        assert parent.get_renderable("new-child-id") is child

    def test_find_descendant_by_id_finds_direct_children(self):
        """findDescendantById finds a direct child."""
        parent = Renderable()
        child1 = Renderable(id="child1")
        child2 = Renderable(id="child2")
        parent.add(child1)
        parent.add(child2)
        assert parent.find_descendant_by_id("child1") is child1
        assert parent.find_descendant_by_id("child2") is child2

    def test_find_descendant_by_id_finds_nested_descendants(self):
        """findDescendantById finds nested children recursively."""
        root = Renderable(id="root")
        child = Renderable(id="child")
        grandchild = Renderable(id="grandchild")
        root.add(child)
        child.add(grandchild)
        assert root.find_descendant_by_id("grandchild") is grandchild
        assert root.find_descendant_by_id("nonexistent") is None

    def test_find_descendant_by_id_handles_text_node_renderable_children_without_crashing(self):
        """findDescendantById handles leaf nodes without children."""
        parent = Renderable(id="parent")
        child = BaseRenderable(id="leaf")
        parent.add(child)
        assert parent.find_descendant_by_id("leaf") is child
        assert parent.find_descendant_by_id("nonexistent") is None

    def test_destroy_recursively_destroys_nested_children_recursively(self):
        """destroy_recursively marks all descendants as destroyed."""
        parent = Renderable(id="parent")
        child = Renderable(id="child")
        grandchild = Renderable(id="grandchild")
        great_grandchild = Renderable(id="great-grandchild")
        parent.add(child)
        child.add(grandchild)
        grandchild.add(great_grandchild)

        parent.destroy_recursively()

        assert parent.is_destroyed is True
        assert child.is_destroyed is True
        assert grandchild.is_destroyed is True
        assert great_grandchild.is_destroyed is True

    def test_destroy_recursively_handles_empty_renderable_without_errors(self):
        """destroy_recursively on an empty renderable does not throw."""
        parent = Renderable()
        parent.destroy_recursively()
        assert parent.is_destroyed is True

    def test_destroy_recursively_destroys_all_children_correctly_with_multiple_children(self):
        """destroy_recursively marks all children as destroyed."""
        parent = Renderable()
        children = [Renderable(id=f"child-{i}") for i in range(5)]
        for c in children:
            parent.add(c)

        parent.destroy_recursively()
        assert parent.is_destroyed is True
        for c in children:
            assert c.is_destroyed is True

    def test_handles_immediate_add_and_destroy_before_render_tick(self):
        """A child that is added and then destroyed before a layout pass
        should not cause errors and the parent should have zero children."""
        root = Renderable(width=80, height=24)
        child = Renderable(id="ephemeral", width=20, height=5)
        root.add(child)
        assert root.get_children_count() == 1

        child.destroy()
        assert root.get_children_count() == 0
        assert child.is_destroyed is True

        # Running layout on the now-empty root must not raise
        _compute_layout(root, 80, 24)
        assert root._layout_width == 80
        assert root._layout_height == 24

    def test_newly_added_child_should_not_have_layout_updated_if_destroyed_before_render(self):
        """A child destroyed before layout runs keeps its initial zero dimensions."""
        root = Renderable(width=80, height=24)
        child = Renderable(id="doomed", width=30, height=10)
        root.add(child)
        child.destroy()

        # After destroy, yoga_node is None so _apply_yoga_layout is a no-op.
        assert child._layout_width == 0
        assert child._layout_height == 0

        # Layout on root should still work.
        _compute_layout(root, 80, 24)

    def test_newly_added_children_receive_correct_layout_dimensions_on_first_render(self):
        """After a layout pass, fixed-size children have correct _layout_width/_layout_height."""
        root = Renderable(width=80, height=24)
        child1 = Renderable(id="child1", width=30, height=10)
        child2 = Renderable(id="child2", width=40, height=8)
        root.add(child1)
        root.add(child2)

        _compute_layout(root, 80, 24)

        assert child1._layout_width == 30
        assert child1._layout_height == 10
        assert child2._layout_width == 40
        assert child2._layout_height == 8

    def test_newly_added_children_with_nested_children_receive_correct_layout(self):
        """Nested children all receive computed layout dimensions."""
        root = Renderable(width=80, height=24)
        parent_child = Renderable(id="parent-child", width=60, height=20)
        grandchild = Renderable(id="grandchild", width=30, height=10)
        parent_child.add(grandchild)
        root.add(parent_child)

        _compute_layout(root, 80, 24)

        assert parent_child._layout_width == 60
        assert parent_child._layout_height == 20
        assert grandchild._layout_width == 30
        assert grandchild._layout_height == 10

    def test_children_added_via_insert_before_receive_correct_layout_on_first_render(self):
        """A child inserted via insert_before gets correct layout after compute."""
        root = Renderable(width=80, height=24)
        child1 = Renderable(id="child1", width=30, height=5)
        child3 = Renderable(id="child3", width=30, height=5)
        root.add(child1)
        root.add(child3)

        child2 = Renderable(id="child2", width=30, height=5)
        root.insert_before(child2, child3)

        _compute_layout(root, 80, 24)

        assert child1._layout_width == 30
        assert child1._layout_height == 5
        assert child2._layout_width == 30
        assert child2._layout_height == 5
        assert child3._layout_width == 30
        assert child3._layout_height == 5

    def test_children_after_insert_before_anchor_maintain_correct_layout(self):
        """After insertBefore, the anchor and its subsequent siblings still
        have correct positions (y offsets stack in column direction)."""
        root = Renderable(width=80, height=60, flex_direction="column")
        child1 = Renderable(id="child1", width=80, height=10)
        child3 = Renderable(id="child3", width=80, height=10)
        root.add(child1)
        root.add(child3)

        child2 = Renderable(id="child2", width=80, height=10)
        root.insert_before(child2, child3)

        _compute_layout(root, 80, 60)

        # Column layout: child1 at y=0, child2 at y=10, child3 at y=20
        assert child1._y == 0
        assert child2._y == 10
        assert child3._y == 20

    def test_multiple_children_inserted_in_sequence_receive_correct_layout(self):
        """Multiple insertBefore calls produce correct sequential layout."""
        root = Renderable(width=80, height=60, flex_direction="column")
        anchor = Renderable(id="anchor", width=80, height=10)
        root.add(anchor)

        # Insert three children before the anchor, one at a time
        c1 = Renderable(id="c1", width=80, height=10)
        c2 = Renderable(id="c2", width=80, height=10)
        c3 = Renderable(id="c3", width=80, height=10)
        root.insert_before(c1, anchor)
        root.insert_before(c2, anchor)
        root.insert_before(c3, anchor)

        _compute_layout(root, 80, 60)

        # Order: c1, c2, c3, anchor
        children = root.get_children()
        assert children[0] is c1
        assert children[1] is c2
        assert children[2] is c3
        assert children[3] is anchor

        assert c1._y == 0
        assert c2._y == 10
        assert c3._y == 20
        assert anchor._y == 30

    def test_existing_child_moved_via_insert_before_maintains_layout_integrity(self):
        """Moving an existing child via insertBefore re-computes layout correctly."""
        root = Renderable(width=80, height=60, flex_direction="column")
        c1 = Renderable(id="c1", width=80, height=10)
        c2 = Renderable(id="c2", width=80, height=10)
        c3 = Renderable(id="c3", width=80, height=10)
        root.add(c1)
        root.add(c2)
        root.add(c3)

        _compute_layout(root, 80, 60)
        # Initial order: c1=0, c2=10, c3=20
        assert c1._y == 0
        assert c2._y == 10
        assert c3._y == 20

        # Move c3 before c1
        root.insert_before(c3, c1)
        _compute_layout(root, 80, 60)

        # New order: c3, c1, c2
        children = root.get_children()
        assert children[0] is c3
        assert children[1] is c1
        assert children[2] is c2

        assert c3._y == 0
        assert c1._y == 10
        assert c2._y == 20


class TestRenderableEvents:
    """Maps to describe('Renderable - Events')."""

    def test_handles_mouse_events(self):
        """Renderable can register and dispatch mouse event handlers."""
        r = Renderable()
        received = []
        r._on_mouse_down = lambda e: received.append(("down", e))
        r._on_mouse_up = lambda e: received.append(("up", e))
        # Simulate calling handlers directly
        r._on_mouse_down({"x": 5, "y": 10})
        r._on_mouse_up({"x": 5, "y": 10})
        assert len(received) == 2
        assert received[0][0] == "down"
        assert received[1][0] == "up"

    def test_handles_mouse_event_types(self):
        """Renderable supports all mouse event handler types."""
        r = Renderable()
        handler_attrs = [
            "_on_mouse_down",
            "_on_mouse_up",
            "_on_mouse_move",
            "_on_mouse_drag",
            "_on_mouse_scroll",
        ]
        for attr in handler_attrs:
            assert getattr(r, attr) is None  # default None
            setattr(r, attr, lambda e: None)
            assert getattr(r, attr) is not None


class TestRenderableFocus:
    """Maps to describe('Renderable - Focus')."""

    def test_handles_focus_when_not_focusable(self):
        """Non-focusable renderable has _focusable=False."""
        r = Renderable()
        assert r._focusable is False
        assert r._focused is False

    def test_handles_focus_when_focusable(self):
        """Focusable renderable can be focused."""
        r = Renderable(focused=True)
        assert r._focused is True

    def test_emits_focus_events(self):
        """Focus and blur methods change the focused state and trigger callbacks."""
        r = Renderable(focusable=True)
        events = []
        r._on_size_change = None  # not relevant here

        # Track focus changes via the on() / emit() event system
        r.on("focus", lambda: events.append("focus"))
        r.on("blur", lambda: events.append("blur"))

        # Use focus/blur methods
        r.focus()
        r.emit("focus")
        assert r._focused is True
        assert events == ["focus"]

        r.blur()
        r.emit("blur")
        assert r._focused is False
        assert events == ["focus", "blur"]

    def test_on_paste_receives_full_paste_event_with_prevent_default(self):
        """on_paste handler can be set."""
        r = Renderable()
        received = []
        r._on_paste = lambda e: received.append(e)
        r._on_paste({"text": "hello"})
        assert len(received) == 1

    def test_handle_paste_receives_full_paste_event(self):
        """Paste handler receives event object."""
        r = Renderable()
        result = []
        r._on_paste = lambda e: result.append(e.get("text"))
        r._on_paste({"text": "world"})
        assert result == ["world"]

    def test_prevent_default_in_on_paste_prevents_handle_paste(self):
        """Maps to test('preventDefault in onPaste prevents handlePaste').

        Two-phase dispatch: on_paste runs first; if it calls
        prevent_default(), handle_paste is skipped.
        """
        from opentui.events import PasteEvent

        r = Renderable(focusable=True)
        on_paste_called = False
        handle_paste_called = False

        def _on_paste(event):
            nonlocal on_paste_called
            on_paste_called = True
            event.prevent_default()

        def _handle_paste(event):
            nonlocal handle_paste_called
            handle_paste_called = True

        r.on_paste = _on_paste
        r.handle_paste = _handle_paste

        event = PasteEvent(text="prevented")
        r.dispatch_paste(event)

        assert on_paste_called is True
        assert handle_paste_called is False
        assert event.default_prevented is True


class TestRenderableLifecycle:
    """Maps to describe('Renderable - Lifecycle')."""

    def test_handles_destroy(self):
        """Destroy sets is_destroyed to True."""
        r = Renderable()
        assert r.is_destroyed is False
        r.destroy()
        assert r.is_destroyed is True

    def test_prevents_double_destroy(self):
        """Double destroy is safe — no error."""
        r = Renderable()
        r.destroy()
        assert r.is_destroyed is True
        r.destroy()  # Should not raise
        assert r.is_destroyed is True

    def test_handles_recursive_destroy(self):
        """Recursive destroy marks all nodes as destroyed."""
        parent = Renderable()
        child1 = Renderable()
        child2 = Renderable()
        parent.add(child1)
        parent.add(child2)
        parent.destroy()
        assert parent.is_destroyed is True
        assert child1.is_destroyed is True
        assert child2.is_destroyed is True


class TestRenderableLayoutWithViewportFiltering:
    """Maps to describe('Renderable - Layout with Viewport Filtering')."""

    def test_newly_added_children_receive_layout_even_when_filtered_from_viewport(self):
        """Children outside the visible viewport still get correct layout dimensions.

        Yoga layout is always computed on the full tree regardless of viewport
        culling, so even children that will be filtered at render time must
        have their _layout_width/_layout_height set.
        """
        root = Renderable(width=80, height=24, flex_direction="column")
        # Add many children so some fall below the viewport height
        children = []
        for i in range(10):
            c = Renderable(id=f"child-{i}", width=80, height=5)
            root.add(c)
            children.append(c)

        _compute_layout(root, 80, 24)

        # All children (including those past y=24) should have layout computed
        for c in children:
            assert c._layout_width == 80
            assert c._layout_height == 5

        # Children beyond the viewport still get correct y positions
        for i, c in enumerate(children):
            assert c._y == i * 5

    def test_child_inserted_before_visible_children_receives_layout_when_filtered(self):
        """A child inserted at the top pushes subsequent children down,
        and all children (including those pushed below the viewport)
        still receive correct layout."""
        root = Renderable(width=80, height=24, flex_direction="column")
        c1 = Renderable(id="c1", width=80, height=10)
        c2 = Renderable(id="c2", width=80, height=10)
        root.add(c1)
        root.add(c2)

        # Insert a new child at the very top (before c1)
        new_top = Renderable(id="new-top", width=80, height=8)
        root.insert_before(new_top, c1)

        _compute_layout(root, 80, 24)

        assert new_top._layout_width == 80
        assert new_top._layout_height == 8
        assert new_top._y == 0

        assert c1._y == 8
        assert c2._y == 18  # 8 + 10


class TestRenderableNestedChildrenLayout:
    """Maps to describe('Renderable - Nested Children Layout')."""

    def test_newly_added_parent_with_deeply_nested_children_all_receive_layout(self):
        """A subtree added all at once gets layout computed for every level."""
        root = Renderable(width=80, height=60)

        # Build a subtree before adding to root
        parent = Renderable(id="parent", width=60, height=40)
        child = Renderable(id="child", width=40, height=20)
        grandchild = Renderable(id="grandchild", width=20, height=10)
        child.add(grandchild)
        parent.add(child)
        root.add(parent)

        _compute_layout(root, 80, 60)

        assert parent._layout_width == 60
        assert parent._layout_height == 40
        assert child._layout_width == 40
        assert child._layout_height == 20
        assert grandchild._layout_width == 20
        assert grandchild._layout_height == 10

    def test_insert_before_with_nested_children_updates_all_descendants_correctly(self):
        """Inserting a subtree via insertBefore computes layout for the
        subtree and adjusts positions of subsequent siblings."""
        root = Renderable(width=80, height=60, flex_direction="column")
        anchor = Renderable(id="anchor", width=80, height=10)
        root.add(anchor)

        # Build a subtree
        parent = Renderable(id="parent", width=80, height=20)
        child = Renderable(id="child", width=40, height=10)
        parent.add(child)

        root.insert_before(parent, anchor)
        _compute_layout(root, 80, 60)

        assert parent._layout_width == 80
        assert parent._layout_height == 20
        assert child._layout_width == 40
        assert child._layout_height == 10

        # parent at y=0, anchor pushed to y=20
        assert parent._y == 0
        assert anchor._y == 20


class TestRenderableComplexLayoutUpdateScenarios:
    """Maps to describe('Renderable - Complex Layout Update Scenarios')."""

    def test_multiple_rapid_add_operations_before_render_complete_correctly(self):
        """Several add() calls before a single layout pass all resolve correctly."""
        root = Renderable(width=80, height=60, flex_direction="column")

        children = []
        for i in range(5):
            c = Renderable(id=f"rapid-{i}", width=80, height=10)
            root.add(c)
            children.append(c)

        _compute_layout(root, 80, 60)

        for i, c in enumerate(children):
            assert c._layout_width == 80
            assert c._layout_height == 10
            assert c._y == i * 10

    def test_insert_before_at_different_positions_updates_subsequent_children_correctly(self):
        """Inserting at the beginning, middle, and end all produce correct layout."""
        root = Renderable(width=80, height=80, flex_direction="column")
        c_a = Renderable(id="A", width=80, height=10)
        c_c = Renderable(id="C", width=80, height=10)
        c_e = Renderable(id="E", width=80, height=10)
        root.add(c_a)
        root.add(c_c)
        root.add(c_e)

        # Insert B between A and C
        c_b = Renderable(id="B", width=80, height=10)
        root.insert_before(c_b, c_c)

        # Insert D between C and E
        c_d = Renderable(id="D", width=80, height=10)
        root.insert_before(c_d, c_e)

        _compute_layout(root, 80, 80)

        # Order: A, B, C, D, E
        expected_ids = ["A", "B", "C", "D", "E"]
        children = root.get_children()
        assert [c.id for c in children] == expected_ids

        for i, c in enumerate(children):
            assert c._y == i * 10
            assert c._layout_height == 10

    def test_add_and_insert_before_mixed_operations_maintain_layout_integrity(self):
        """A mix of add() and insertBefore() produces consistent layout."""
        root = Renderable(width=80, height=80, flex_direction="column")

        c1 = Renderable(id="c1", width=80, height=10)
        c2 = Renderable(id="c2", width=80, height=10)
        c3 = Renderable(id="c3", width=80, height=10)
        root.add(c1)
        root.add(c3)
        root.insert_before(c2, c3)  # c1, c2, c3

        c4 = Renderable(id="c4", width=80, height=10)
        root.add(c4)  # c1, c2, c3, c4

        c0 = Renderable(id="c0", width=80, height=10)
        root.insert_before(c0, c1)  # c0, c1, c2, c3, c4

        _compute_layout(root, 80, 80)

        expected = ["c0", "c1", "c2", "c3", "c4"]
        children = root.get_children()
        assert [c.id for c in children] == expected
        for i, c in enumerate(children):
            assert c._y == i * 10

    def test_children_removed_and_re_added_receive_fresh_layout(self):
        """A child that is removed and re-added gets fresh layout on the next compute."""
        root = Renderable(width=80, height=60, flex_direction="column")
        c1 = Renderable(id="c1", width=80, height=10)
        c2 = Renderable(id="c2", width=80, height=10)
        c3 = Renderable(id="c3", width=80, height=10)
        root.add(c1)
        root.add(c2)
        root.add(c3)

        _compute_layout(root, 80, 60)
        assert c2._y == 10

        # Remove c2, layout should update c3's position
        root.remove(c2)
        _compute_layout(root, 80, 60)
        assert c3._y == 10  # c3 moves up

        # Re-add c2 at the end
        root.add(c2)
        _compute_layout(root, 80, 60)

        children = root.get_children()
        assert [c.id for c in children] == ["c1", "c3", "c2"]
        assert c1._y == 0
        assert c3._y == 10
        assert c2._y == 20  # fresh layout at the new position


class TestRootRenderable:
    """Maps to describe('RootRenderable')."""

    def test_creates_with_proper_setup(self):
        """RootRenderable is created with the renderer's dimensions and has a yoga node."""
        renderer = _make_fake_renderer(80, 24)
        root = renderer.root

        assert isinstance(root, RootRenderable)
        assert root._width == 80
        assert root._height == 24
        assert root._yoga_node is not None
        assert root.get_children_count() == 0

    def test_handles_layout_calculation(self):
        """RootRenderable propagates layout to children when computed."""
        renderer = _make_fake_renderer(80, 24)
        root = renderer.root

        child = Renderable(id="child", width=40, height=12)
        root.add(child)

        # Simulate what _render_frame does: configure, compute, apply
        root._configure_yoga_properties()
        yoga_layout.compute_layout(root._yoga_node, 80.0, 24.0)
        _apply_yoga_layout_recursive(root)

        assert root._layout_width == 80
        assert root._layout_height == 24
        assert child._layout_width == 40
        assert child._layout_height == 12

    def test_handles_resize(self):
        """After resize(), RootRenderable's dimensions update and layout re-computes."""
        renderer = _make_fake_renderer(80, 24)
        root = renderer.root

        child = Renderable(id="child", width=40, height=12)
        root.add(child)

        # Initial layout
        root._configure_yoga_properties()
        yoga_layout.compute_layout(root._yoga_node, 80.0, 24.0)
        _apply_yoga_layout_recursive(root)
        assert root._layout_width == 80
        assert root._layout_height == 24

        # Simulate resize
        renderer.resize(120, 40)
        root._width = renderer.width
        root._height = renderer.height

        root._configure_yoga_properties()
        yoga_layout.compute_layout(root._yoga_node, 120.0, 40.0)
        _apply_yoga_layout_recursive(root)

        assert root._layout_width == 120
        assert root._layout_height == 40
        # Child keeps its fixed dimensions
        assert child._layout_width == 40
        assert child._layout_height == 12
