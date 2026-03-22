"""Port of upstream box.test.tsx.

Upstream: packages/solid/tests/box.test.tsx
Tests ported: 1/1 (0 skipped)
"""

from opentui import test_render as _test_render
from opentui.components.box import Box
from opentui.components.scrollbox import ScrollBox
from opentui.signals import Signal


async def _strict_render(component_fn, options):
    merged = dict(options)
    return await _test_render(component_fn, merged)


class TestBoxComponent:
    """Maps to describe("Box Component")."""

    async def test_should_support_focusable_prop_and_controlled_focus_state(self):
        """Maps to it("should support focusable prop and controlled focus state")."""

        focused = Signal(False, name="focused")

        def make_box():
            return Box(
                focusable=True,
                focused=focused,
                width=10,
                height=5,
                border=True,
            )

        setup = await _strict_render(
            make_box,
            {"width": 15, "height": 8},
        )

        # Initial render
        setup.render_frame()

        # Get the box renderable from the root's children
        box_ref = setup.renderer.root.get_children()[0]

        assert box_ref.focusable is True
        assert box_ref.focused is False

        # Update focused signal to True through reactive prop binding
        focused.set(True)
        setup.render_frame()

        box_ref = setup.renderer.root.get_children()[0]
        assert box_ref.focused is True

        # Update focused signal back to False through reactive prop binding
        focused.set(False)
        setup.render_frame()

        box_ref = setup.renderer.root.get_children()[0]
        assert box_ref.focused is False

        setup.destroy()


class TestRenderBefore:
    """Tests for render_before callback in Box and ScrollBox."""

    async def test_box_render_before_called(self):
        """render_before fires with (buffer, dt, box) in Box.render()."""
        calls = []

        def on_before(buffer, dt, node):
            calls.append(("before", type(node).__name__))

        def make_box():
            box = Box(width=10, height=5)
            box._render_before = on_before
            return box

        setup = await _strict_render(make_box, {"width": 20, "height": 10})
        setup.render_frame()

        assert len(calls) == 1
        assert calls[0] == ("before", "Box")
        setup.destroy()

    async def test_scrollbox_render_before_called(self):
        """render_before fires with (buffer, dt, scrollbox) in ScrollBox.render()."""
        calls = []

        def on_before(buffer, dt, node):
            calls.append(("before", type(node).__name__))

        def make_scrollbox():
            sb = ScrollBox(width=10, height=5, scroll_y=True)
            sb._render_before = on_before
            return sb

        setup = await _strict_render(make_scrollbox, {"width": 20, "height": 10})
        setup.render_frame()

        assert len(calls) == 1
        assert calls[0] == ("before", "ScrollBox")
        setup.destroy()
