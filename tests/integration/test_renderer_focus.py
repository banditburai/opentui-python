"""Port of upstream renderer.focus.test.ts.

Upstream: packages/core/src/tests/renderer.focus.test.ts
Tests ported: 10/10 (0 skipped)

These tests verify that clicking on focusable elements gives them focus
(auto-focus on left-click), that focus bubbles up the tree to the nearest
focusable ancestor, that only left-clicks trigger auto-focus, that
preventDefault() on mousedown blocks auto-focus, and that dragging does not
auto-focus the drag target.
"""

import pytest

from opentui import create_test_renderer
from opentui.components.box import Box
from opentui.components.scrollbox import ScrollBox
from opentui.components.control_flow import Portal, Show
from opentui.events import MouseButton, MouseEvent
from opentui.signals import Signal


def _render_and_layout(setup):
    """Run one frame so yoga layout is computed and positions are known."""
    setup.render_frame()


class TestRendererFocus:
    """Maps to top-level tests in renderer.focus.test.ts."""

    async def test_click_on_focusable_element_focuses_it(self):
        """Maps to test("click on focusable element focuses it")."""

        setup = await create_test_renderer(50, 30)
        try:
            scrollbox = ScrollBox(
                width=20,
                height=10,
                focusable=True,
                position="absolute",
                left=0,
                top=0,
            )
            setup.renderer.root.add(scrollbox)
            _render_and_layout(setup)

            assert scrollbox.focused is False

            # Dispatch a left-button mousedown inside the scrollbox.
            event = MouseEvent(
                type="down", x=scrollbox.x + 1, y=scrollbox.y + 1, button=MouseButton.LEFT
            )
            setup.renderer._dispatch_mouse_event(event)

            assert scrollbox.focused is True
        finally:
            setup.destroy()

    async def test_click_on_child_bubbles_up_to_focusable_parent(self):
        """Maps to test("click on child bubbles up to focusable parent")."""

        setup = await create_test_renderer(50, 30)
        try:
            from opentui.components.text_renderable import TextRenderable

            scrollbox = ScrollBox(
                width=20,
                height=10,
                focusable=True,
                position="absolute",
                left=0,
                top=0,
            )
            setup.renderer.root.add(scrollbox)

            text = TextRenderable(content="Click me", position="relative")
            scrollbox.add(text)
            _render_and_layout(setup)

            assert scrollbox.focused is False

            # Click inside the scrollbox.
            event = MouseEvent(
                type="down", x=scrollbox.x + 1, y=scrollbox.y + 1, button=MouseButton.LEFT
            )
            setup.renderer._dispatch_mouse_event(event)

            # Focus should bubble to the parent.
            assert scrollbox.focused is True
        finally:
            setup.destroy()

    async def test_click_on_non_focusable_with_no_focusable_parent_does_nothing(self):
        """Maps to test("click on non-focusable with no focusable parent does nothing")."""

        setup = await create_test_renderer(50, 30)
        try:
            box = Box(
                width=20,
                height=10,
                position="absolute",
                left=0,
                top=0,
            )
            setup.renderer.root.add(box)
            _render_and_layout(setup)

            assert box.focusable is False

            event = MouseEvent(type="down", x=box.x + 1, y=box.y + 1, button=MouseButton.LEFT)
            setup.renderer._dispatch_mouse_event(event)

            assert box.focused is False
        finally:
            setup.destroy()

    async def test_prevent_default_on_mousedown_prevents_auto_focus(self):
        """Maps to test("preventDefault on mousedown prevents auto-focus")."""

        setup = await create_test_renderer(50, 30)
        try:
            scrollbox = ScrollBox(
                width=20,
                height=10,
                focusable=True,
                position="absolute",
                left=0,
                top=0,
            )

            def _on_mouse_down(event):
                event.prevent_default()

            scrollbox._on_mouse_down = _on_mouse_down
            setup.renderer.root.add(scrollbox)
            _render_and_layout(setup)

            assert scrollbox.focused is False

            event = MouseEvent(
                type="down", x=scrollbox.x + 1, y=scrollbox.y + 1, button=MouseButton.LEFT
            )
            setup.renderer._dispatch_mouse_event(event)

            # preventDefault was called, so auto-focus should be blocked.
            assert scrollbox.focused is False
        finally:
            setup.destroy()

    async def test_mousedown_handler_is_only_called_once_per_click(self):
        """Maps to test("mousedown handler is only called once per click")."""

        setup = await create_test_renderer(50, 30)
        try:
            mouse_down_count = 0

            box = Box(
                width=20,
                height=10,
                position="absolute",
                left=0,
                top=0,
            )

            def _on_mouse_down(event):
                nonlocal mouse_down_count
                mouse_down_count += 1

            box._on_mouse_down = _on_mouse_down
            setup.renderer.root.add(box)
            _render_and_layout(setup)

            # Simulate a full click (down + up).
            down_event = MouseEvent(type="down", x=box.x + 1, y=box.y + 1, button=MouseButton.LEFT)
            up_event = MouseEvent(type="up", x=box.x + 1, y=box.y + 1, button=MouseButton.LEFT)
            setup.renderer._dispatch_mouse_event(down_event)
            setup.renderer._dispatch_mouse_event(up_event)

            assert mouse_down_count == 1
        finally:
            setup.destroy()

    async def test_non_left_click_does_not_auto_focus(self):
        """Maps to test("non-left click does not auto-focus")."""

        setup = await create_test_renderer(50, 30)
        try:
            scrollbox = ScrollBox(
                width=20,
                height=10,
                focusable=True,
                position="absolute",
                left=0,
                top=0,
            )
            setup.renderer.root.add(scrollbox)
            _render_and_layout(setup)

            # Right-click should not auto-focus.
            event = MouseEvent(
                type="down", x=scrollbox.x + 1, y=scrollbox.y + 1, button=MouseButton.RIGHT
            )
            setup.renderer._dispatch_mouse_event(event)
            assert scrollbox.focused is False

            # Middle-click should not auto-focus.
            event2 = MouseEvent(
                type="down", x=scrollbox.x + 2, y=scrollbox.y + 2, button=MouseButton.MIDDLE
            )
            setup.renderer._dispatch_mouse_event(event2)
            assert scrollbox.focused is False
        finally:
            setup.destroy()

    async def test_prevent_default_on_ancestor_blocks_auto_focus(self):
        """Maps to test("preventDefault on ancestor blocks auto-focus")."""

        setup = await create_test_renderer(50, 30)
        try:
            child_down = False

            parent = Box(
                width=20,
                height=10,
                focusable=True,
                position="absolute",
                left=2,
                top=2,
            )

            def _parent_mouse_down(event):
                event.prevent_default()

            parent._on_mouse_down = _parent_mouse_down

            child = Box(
                width=6,
                height=3,
                position="absolute",
                left=1,
                top=1,
            )

            def _child_mouse_down(event):
                nonlocal child_down
                child_down = True

            child._on_mouse_down = _child_mouse_down

            parent.add(child)
            setup.renderer.root.add(parent)
            _render_and_layout(setup)

            # Click inside the child (which is inside the parent).
            # Use computed positions to avoid out-of-bounds clicks.
            click_x = child.x + 1 if child._layout_width > 0 else parent.x + 2
            click_y = child.y + 1 if child._layout_height > 0 else parent.y + 2
            event = MouseEvent(type="down", x=click_x, y=click_y, button=MouseButton.LEFT)
            setup.renderer._dispatch_mouse_event(event)

            assert child_down is True
            assert parent.focused is False
            assert child.focused is False
        finally:
            setup.destroy()

    async def test_dragging_over_focusable_target_does_not_auto_focus(self):
        """Maps to test("dragging over focusable target does not auto-focus")."""

        setup = await create_test_renderer(50, 30)
        try:
            start = Box(
                width=6,
                height=4,
                position="absolute",
                left=1,
                top=1,
            )

            focusable = Box(
                width=6,
                height=4,
                focusable=True,
                position="absolute",
                left=12,
                top=1,
            )

            setup.renderer.root.add(start)
            setup.renderer.root.add(focusable)
            _render_and_layout(setup)

            # Press down on the start element.
            press_x = start.x + 1 if start._layout_width > 0 else 2
            press_y = start.y + 1 if start._layout_height > 0 else 2
            down_event = MouseEvent(type="down", x=press_x, y=press_y, button=MouseButton.LEFT)
            setup.renderer._dispatch_mouse_event(down_event)

            # Drag to the focusable element.
            drag_x = focusable.x + 1 if focusable._layout_width > 0 else 13
            drag_y = focusable.y + 1 if focusable._layout_height > 0 else 2
            drag_event = MouseEvent(
                type="drag", x=drag_x, y=drag_y, button=MouseButton.LEFT, is_dragging=True
            )
            setup.renderer._dispatch_mouse_event(drag_event)

            # Release on the focusable element.
            up_event = MouseEvent(type="up", x=drag_x, y=drag_y, button=MouseButton.LEFT)
            setup.renderer._dispatch_mouse_event(up_event)

            # The focusable element should NOT be focused because this was a drag.
            assert focusable.focused is False
        finally:
            setup.destroy()

    async def test_clicking_empty_space_does_not_auto_focus(self):
        """Maps to test("clicking empty space does not auto-focus")."""

        setup = await create_test_renderer(50, 30)
        try:
            box = Box(
                width=8,
                height=4,
                focusable=True,
                position="absolute",
                left=1,
                top=1,
            )
            setup.renderer.root.add(box)
            _render_and_layout(setup)

            # Click far outside the box (empty space).
            event = MouseEvent(
                type="down",
                x=setup.renderer.width - 1,
                y=setup.renderer.height - 1,
                button=MouseButton.LEFT,
            )
            setup.renderer._dispatch_mouse_event(event)

            assert box.focused is False
        finally:
            setup.destroy()

    async def test_auto_focus_false_prevents_click_focus_changes(self):
        """Maps to test("autoFocus=false prevents click focus changes")."""

        setup = await create_test_renderer(50, 30, auto_focus=False)
        try:
            first = Box(
                width=8,
                height=4,
                focusable=True,
                position="absolute",
                left=1,
                top=1,
            )
            second = Box(
                width=8,
                height=4,
                focusable=True,
                position="absolute",
                left=12,
                top=1,
            )
            setup.renderer.root.add(first)
            setup.renderer.root.add(second)
            _render_and_layout(setup)

            # Manually focus the first element.
            first.focus()
            assert first.focused is True

            # Click on the second element — with auto_focus=False no focus change.
            click_x = second.x + 1 if second._layout_width > 0 else 13
            click_y = second.y + 1 if second._layout_height > 0 else 2
            event = MouseEvent(type="down", x=click_x, y=click_y, button=MouseButton.LEFT)
            setup.renderer._dispatch_mouse_event(event)

            assert first.focused is True
            assert second.focused is False
        finally:
            setup.destroy()

    async def test_portal_overlay_focuses_overlay_and_unmounts_cleanly_when_hidden(self):
        """Portal overlay should win focus while visible and release it when hidden."""
        setup = await create_test_renderer(50, 30)
        try:
            visible = Signal(True, name="visible")

            background = Box(
                width=12,
                height=6,
                focusable=True,
                position="absolute",
                left=1,
                top=1,
            )
            setup.renderer.root.add(background)

            overlay_show = Show(
                when=lambda: visible(),
                render=lambda: Portal(
                    Box(
                        width=12,
                        height=6,
                        focusable=True,
                        position="absolute",
                        left=1,
                        top=1,
                    ),
                    key="portal",
                ),
                key="overlay-show",
            )
            setup.renderer.root.add(overlay_show)
            _render_and_layout(setup)

            click_event = MouseEvent(
                type="down", x=background.x + 1, y=background.y + 1, button=MouseButton.LEFT
            )
            setup.renderer._dispatch_mouse_event(click_event)

            portal_container = next(
                child
                for child in setup.renderer.root._children
                if getattr(child, "key", None) == "portal-container-portal"
            )
            overlay = portal_container._children[0]

            assert overlay.focused is True
            assert background.focused is False

            visible.set(False)
            _render_and_layout(setup)

            assert not any(
                getattr(child, "key", None) == "portal-container-portal"
                for child in setup.renderer.root._children
            )

            background_click = MouseEvent(
                type="down",
                x=background.x + 1,
                y=background.y + 1,
                button=MouseButton.LEFT,
            )
            setup.renderer._dispatch_mouse_event(background_click)

            assert background.focused is True
        finally:
            setup.destroy()
