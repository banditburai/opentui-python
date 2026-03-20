"""Tests for Portal component — renders children at a different tree location.

Tests ported from upstream dynamic-portal.test.tsx + unit tests for
destruction ordering, ref callback, _host, and display=none marker.
"""

import pytest

from opentui import create_test_renderer
from opentui.components.base import BaseRenderable, Renderable
from opentui.components.box import Box
from opentui.components.text import Text
from opentui.components.control_flow import Match, Portal, Show, Switch
from opentui.hooks import set_renderer
from opentui.reconciler import reconcile, _init_nested_fors
from opentui.renderer import CliRenderer, CliRendererConfig, RootRenderable
from opentui.signals import Signal
from opentui import layout as yoga_layout

from tests.conftest import FakeNative


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_root():
    """Create a root renderable simulating renderer.root."""
    return Renderable(key="root", width=80, height=24)


# ---------------------------------------------------------------------------
# Unit tests (no renderer needed)
# ---------------------------------------------------------------------------


class TestPortalUnit:
    def test_marker_display_none(self):
        """Portal marker node has display=none after configure."""
        root = _make_root()
        portal = Portal(
            Renderable(key="child"),
            mount=root,
            key="portal",
        )
        parent = Renderable(key="parent")
        parent.add(portal)
        root.add(parent)

        # Configure triggers _ensure_container and sets display=none
        portal._pre_configure_yoga()
        portal._configure_yoga_node(portal._yoga_node)
        portal._post_configure_yoga(portal._yoga_node)

        # Portal's own _children should be empty (marker only)
        assert len(portal._children) == 0
        # Container should exist on root
        assert portal._container is not None
        assert portal._container in root._children

    def test_destroy_removes_container_from_mount(self):
        """Destroying portal removes container from mount point."""
        root = _make_root()
        portal = Portal(
            Renderable(key="child"),
            mount=root,
            key="portal",
        )
        portal._ensure_container()

        assert portal._container in root._children
        container = portal._container

        portal.destroy()

        assert container not in root._children
        assert container._destroyed

    def test_ref_callback_receives_container(self):
        """ref callback is called with the container Box."""
        root = _make_root()
        ref_calls = []
        portal = Portal(
            Renderable(key="child"),
            mount=root,
            ref=lambda c: ref_calls.append(c),
            key="portal",
        )
        portal._ensure_container()

        assert len(ref_calls) == 1
        assert ref_calls[0] is portal._container

    def test_host_property_on_container(self):
        """Container's _host points back to the Portal node."""
        root = _make_root()
        portal = Portal(
            Renderable(key="child"),
            mount=root,
            key="portal",
        )
        portal._ensure_container()

        assert portal._container._host is portal

    def test_destroy_when_mount_already_destroyed(self):
        """Portal.destroy() handles mount already destroyed gracefully."""
        root = _make_root()
        portal = Portal(
            Renderable(key="child"),
            mount=root,
            key="portal",
        )
        portal._ensure_container()
        container = portal._container

        # Destroy mount first
        root.destroy()
        assert root._destroyed

        # Portal destroy should not raise
        portal.destroy()
        assert portal._destroyed
        assert container._destroyed

    def test_destroy_idempotent(self):
        """Calling destroy() twice is safe."""
        root = _make_root()
        portal = Portal(
            Renderable(key="child"),
            mount=root,
            key="portal",
        )
        portal._ensure_container()

        portal.destroy()
        portal.destroy()  # Should not raise
        assert portal._destroyed

    def test_destroy_clears_content_children(self):
        """destroy() releases _content_children references for GC."""
        root = _make_root()
        portal = Portal(
            Renderable(key="child"),
            mount=root,
            key="portal",
        )
        portal._ensure_container()
        assert len(portal._content_children) == 1

        portal.destroy()
        assert len(portal._content_children) == 0

    def test_container_has_key(self):
        """Container Box gets a key derived from Portal's key."""
        root = _make_root()
        portal = Portal(
            Renderable(key="child"),
            mount=root,
            key="modal",
        )
        portal._ensure_container()
        assert portal._container.key == "portal-container-modal"

    def test_default_mount_uses_renderer_root(self):
        """Portal with mount=None mounts to renderer.root."""
        config = CliRendererConfig(width=80, height=24, testing=True)
        renderer = CliRenderer(1, config, FakeNative())
        renderer._root = RootRenderable(renderer)
        set_renderer(renderer)

        portal = Portal(
            Renderable(key="child"),
            key="portal",
        )
        portal._ensure_container()

        assert portal._container is not None
        assert portal._container in renderer.root._children

        portal.destroy()

    def test_default_mount_error_without_renderer(self):
        """Portal with mount=None raises clear error when no renderer active."""
        from opentui import hooks

        old = hooks._current_renderer
        hooks._current_renderer = None
        try:
            portal = Portal(
                Renderable(key="child"),
                key="portal",
            )
            with pytest.raises(RuntimeError, match="requires an active renderer"):
                portal._ensure_container()
        finally:
            hooks._current_renderer = old


# ---------------------------------------------------------------------------
# Ported upstream tests (dynamic-portal.test.tsx equivalents)
# ---------------------------------------------------------------------------


class TestPortalMounting:
    def test_render_to_default_mount_via_explicit_root(self):
        """Portal children appear at the mount point, not in logical parent.

        Upstream: "renders into the portal target" — Portal renders content
        into a separate mount point rather than its logical position.
        """
        root = _make_root()
        wrapper = Box(key="wrapper")
        root.add(wrapper)

        portal = Portal(
            Text("Portal content", key="text"),
            mount=root,
            key="portal",
        )
        wrapper.add(portal)
        portal._pre_configure_yoga()
        portal._configure_yoga_node(portal._yoga_node)
        portal._post_configure_yoga(portal._yoga_node)

        # Portal marker is in wrapper (but invisible)
        assert portal in wrapper._children
        # Content is in root via container
        assert portal._container in root._children
        assert len(portal._container._children) == 1
        assert portal._container._children[0].key == "text"
        # Portal's own children are empty
        assert len(portal._children) == 0

    def test_render_to_custom_mount_point(self):
        """Children mount on a specific Box ref.

        Upstream: "renders into a custom mount point"
        """
        root = _make_root()
        sidebar = Box(key="sidebar")
        root.add(sidebar)

        main = Box(key="main")
        root.add(main)

        portal = Portal(
            Text("Sidebar content", key="sidebar-text"),
            mount=sidebar,
            key="portal",
        )
        main.add(portal)
        portal._pre_configure_yoga()
        portal._configure_yoga_node(portal._yoga_node)
        portal._post_configure_yoga(portal._yoga_node)

        # Content appears in sidebar, not main
        assert portal._container in sidebar._children
        assert len(portal._container._children) == 1
        assert portal._container._children[0].key == "sidebar-text"

    def test_complex_nested_content(self):
        """Multiple children inside Portal.

        Upstream: "renders complex nested content"
        """
        root = _make_root()
        portal = Portal(
            Text("Line 1", key="t1"),
            Text("Line 2", key="t2"),
            Text("Line 3", key="t3"),
            mount=root,
            key="portal",
        )
        portal._ensure_container()

        assert len(portal._container._children) == 3
        assert portal._container._children[0].key == "t1"
        assert portal._container._children[1].key == "t2"
        assert portal._container._children[2].key == "t3"

    def test_cleanup_on_unmount(self):
        """Show + Portal toggling: container removed when Portal destroyed.

        Upstream: "cleans up portal content on unmount"
        """
        root = _make_root()

        visible = True
        show = Show(
            when=lambda: visible,
            render=lambda: Portal(
                Text("Modal", key="modal-text"),
                mount=root,
                key="portal",
            ),
            key="show",
        )
        root.add(show)

        # Configure to trigger _ensure_container
        show._configure_yoga_properties()

        # Portal is active — find it
        portal = show._children[0]
        assert isinstance(portal, Portal)
        portal._ensure_container()

        container = portal._container
        assert container in root._children

        # "Unmount" by destroying the portal (simulating Show toggling off)
        portal.destroy()
        assert container not in root._children
        assert container._destroyed

    def test_show_toggle_reactively_removes_and_recreates_portal_container(self):
        """Show should tear down portal containers on false and recreate on true."""
        root = _make_root()
        visible = Signal(True, name="visible")

        show = Show(
            when=lambda: visible(),
            render=lambda: Portal(
                Text("Modal", key="modal-text"),
                mount=root,
                key="portal",
            ),
            key="show",
        )
        root.add(show)
        show._configure_yoga_properties()

        assert any(getattr(child, "key", None) == "portal-container-portal" for child in root._children)

        visible.set(False)

        assert show._children == []
        assert not any(getattr(child, "key", None) == "portal-container-portal" for child in root._children)

        visible.set(True)
        show._configure_yoga_properties()

        containers = [child for child in root._children if getattr(child, "key", None) == "portal-container-portal"]
        assert len(containers) == 1
        assert containers[0]._children[0].key == "modal-text"

    def test_switch_toggle_reactively_removes_portal_branch(self):
        """Switch should destroy portal branches instead of leaving orphaned containers."""
        root = _make_root()
        mode = Signal("portal", name="mode")

        switch = Switch(
            Match(
                when=lambda: mode() == "portal",
                render=lambda: Portal(
                    Text("Modal", key="modal-text"),
                    mount=root,
                    key="portal",
                ),
            ),
            fallback=lambda: Text("Inline", key="inline"),
            key="switch",
        )
        root.add(switch)
        switch._configure_yoga_properties()

        assert any(getattr(child, "key", None) == "portal-container-portal" for child in root._children)

        mode.set("inline")

        assert len(switch._children) == 1
        assert switch._children[0].key == "inline"
        assert not any(getattr(child, "key", None) == "portal-container-portal" for child in root._children)

    def test_multiple_portals(self):
        """Two Portals coexist at the same mount point.

        Upstream: "supports multiple portals"
        """
        root = _make_root()
        wrapper = Box(key="wrapper")
        root.add(wrapper)

        portal1 = Portal(
            Text("Portal 1", key="p1-text"),
            mount=root,
            key="portal-1",
        )
        portal2 = Portal(
            Text("Portal 2", key="p2-text"),
            mount=root,
            key="portal-2",
        )
        wrapper.add(portal1)
        wrapper.add(portal2)

        portal1._ensure_container()
        portal2._ensure_container()

        # Root has: wrapper + 2 portal containers
        assert len(root._children) == 3
        assert portal1._container in root._children
        assert portal2._container in root._children
        assert portal1._container is not portal2._container

    def test_switch_content_inside_portal(self):
        """Show inside Portal toggles content.

        Adapted from upstream Dynamic+Portal test — uses Show/Signal instead
        of Dynamic since Python has no Dynamic component.
        """
        root = _make_root()
        condition = Signal(True, name="cond")

        def make_portal():
            return Portal(
                Show(
                    when=lambda: condition(),
                    render=lambda: Text("Active", key="active"),
                    fallback=lambda: Text("Inactive", key="inactive"),
                    key="show",
                ),
                mount=root,
                key="portal",
            )

        portal = make_portal()
        portal._ensure_container()

        show = portal._container._children[0]
        assert isinstance(show, Show)
        assert len(show._children) == 1
        assert show._children[0].key == "active"

        # Toggle condition — rebuild via reconciler
        condition.set(False)
        new_portal = make_portal()

        # Reconcile the portal's container children
        old_content = list(portal._container._children)
        new_content = list(new_portal._content_children)
        portal._container._children.clear()
        reconcile(portal._container, old_content, new_content)

        show = portal._container._children[0]
        assert isinstance(show, Show)
        assert len(show._children) == 1
        assert show._children[0].key == "inactive"

    def test_reactive_mount_point(self):
        """Switch mount target between two Boxes via Signal.

        Adapted from upstream Dynamic+Portal test.
        """
        root = _make_root()
        target_a = Box(key="target-a")
        target_b = Box(key="target-b")
        root.add(target_a)
        root.add(target_b)

        use_a = True

        portal = Portal(
            Text("Content", key="content"),
            mount=lambda: target_a if use_a else target_b,
            key="portal",
        )
        portal._ensure_container()

        assert portal._container in target_a._children
        assert portal._container not in target_b._children

        # Switch mount point
        use_a = False
        portal._ensure_container()

        assert portal._container in target_b._children
        assert portal._container not in target_a._children

    def test_portal_in_reconciler_matched(self):
        """Reconciler handles matched Portal nodes, reconciling container children."""
        root = _make_root()
        parent = Renderable(key="parent")

        # First render
        old_portal = Portal(
            Text("V1", key="text"),
            mount=root,
            key="portal",
        )
        old_portal._ensure_container()
        parent._children = [old_portal]
        old_portal._parent = parent

        old_container = old_portal._container
        old_text = old_container._children[0]

        # Second render — text content changed
        new_portal = Portal(
            Text("V2", key="text"),
            mount=root,
            key="portal",
        )

        reconcile(parent, [old_portal], [new_portal])

        # Old portal preserved (same type + key)
        assert parent._children[0] is old_portal
        # Container preserved
        assert old_portal._container is old_container
        # Text node preserved (same key), but patched
        assert old_portal._container._children[0] is old_text

    def test_portal_in_reconciler_new(self):
        """First mount: reconciler initializes new Portal via _init_nested_fors."""
        root = _make_root()
        parent = Renderable(key="parent")

        portal = Portal(
            Text("New", key="text"),
            mount=root,
            key="portal",
        )

        # Wrap in a box to test nested init
        wrapper = Renderable(key="wrapper")
        wrapper.add(portal)

        reconcile(parent, [], [wrapper])

        assert parent._children[0] is wrapper
        found_portal = wrapper._children[0]
        assert isinstance(found_portal, Portal)
        # _init_nested_fors should have called _ensure_container
        assert found_portal._container is not None
        assert found_portal._container in root._children

    def test_portal_vs_non_portal_toggle(self):
        """Signal switches between Portal and direct render.

        When the component function returns a Portal one frame and a direct
        Box the next, reconciler handles the type mismatch correctly.
        """
        root = _make_root()
        parent = Renderable(key="parent")

        # Frame 1: Portal
        portal = Portal(
            Text("Portaled", key="text"),
            mount=root,
            key="content",
        )
        portal._ensure_container()
        parent._children = [portal]
        portal._parent = parent

        container = portal._container
        assert container in root._children

        # Frame 2: Regular Box (different type, same key)
        direct = Box(
            Text("Direct", key="text"),
            key="content",
        )

        reconcile(parent, [portal], [direct])

        # Portal destroyed, container removed
        assert portal._destroyed
        assert container._destroyed
        assert container not in root._children
        # Direct box is now the child
        assert parent._children[0] is direct
        assert parent._children[0].key == "content"


@pytest.mark.asyncio
async def test_clean_portal_overlay_reuses_current_buffer():
    """A clean portal overlay should still qualify for current-buffer replay."""
    setup = await create_test_renderer(60, 20)
    root = setup.renderer.root

    page = Box(width=60, height=20, flex_direction="column")
    for i in range(8):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=12))
        row.add(Text("page content", flex_grow=1))
        page.add(row)

    modal = Box(width=24, height=8, left=18, top=4, border=True, background_color="#112233")
    modal.add(Text("Portal modal", width=18, left=2))
    page.add(Portal(modal, mount=root, key="modal"))
    root.add(page)

    try:
        setup.render_frame()
        setup.render_frame()

        assert setup.renderer._can_reuse_current_buffer_frame()
        assert setup.renderer.last_frame_timings.render_tree_ns < 10_000
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_portal_overlay_remove_reuses_current_buffer(monkeypatch):
    """Portal removal should replay the current buffer instead of full clearing."""
    setup = await create_test_renderer(30, 8)
    try:
        root = setup.renderer.root
        page = Box(width=30, height=8, flex_direction="column")
        page.add(Text("background", width=10))

        overlay = Box(width=10, height=3, left=5, top=2, border=True)
        overlay.add(Text("modal", width=5))
        portal = Portal(overlay, mount=root, key="modal")
        page.add(portal)
        root.add(page)
        setup.render_frame()

        calls = {"copy": 0, "clear": 0}
        native_buffer = setup.renderer._native.buffer
        original_draw_frame_buffer = native_buffer.draw_frame_buffer
        original_clear = native_buffer.buffer_clear

        def counting_draw_frame_buffer(*args, **kwargs):
            calls["copy"] += 1
            return original_draw_frame_buffer(*args, **kwargs)

        def counting_clear(*args, **kwargs):
            calls["clear"] += 1
            return original_clear(*args, **kwargs)

        monkeypatch.setattr(native_buffer, "draw_frame_buffer", counting_draw_frame_buffer)
        monkeypatch.setattr(native_buffer, "buffer_clear", counting_clear)

        page.remove(portal)
        portal.destroy()
        setup.render_frame()

        assert calls["copy"] == 1
        assert calls["clear"] == 0
        assert "modal" not in setup.get_buffer().get_plain_text()
    finally:
        setup.destroy()
