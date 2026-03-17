"""Port of upstream box.test.tsx.

Upstream: packages/solid/tests/box.test.tsx
Tests ported: 1/1 (0 skipped)
"""

from opentui import test_render as _test_render
from opentui.components.box import Box
from opentui.signals import Signal


class TestBoxComponent:
    """Maps to describe("Box Component")."""

    async def test_should_support_focusable_prop_and_controlled_focus_state(self):
        """Maps to it("should support focusable prop and controlled focus state")."""

        focused = Signal("focused", False)

        def make_box():
            return Box(
                focusable=True,
                focused=focused(),
                width=10,
                height=5,
                border=True,
            )

        setup = await _test_render(make_box, {"width": 15, "height": 8})

        # Initial render
        setup.render_frame()

        # Get the box renderable from the root's children
        box_ref = setup.renderer.root.get_children()[0]

        assert box_ref.focusable is True
        assert box_ref.focused is False

        # Update focused signal to True and rebuild component tree
        focused.set(True)
        root = setup.renderer.root
        root._children.clear()
        root._yoga_node.remove_all_children()
        root.add(make_box())
        setup.render_frame()

        box_ref = setup.renderer.root.get_children()[0]
        assert box_ref.focused is True

        # Update focused signal back to False and rebuild
        focused.set(False)
        root = setup.renderer.root
        root._children.clear()
        root._yoga_node.remove_all_children()
        root.add(make_box())
        setup.render_frame()

        box_ref = setup.renderer.root.get_children()[0]
        assert box_ref.focused is False

        setup.destroy()
