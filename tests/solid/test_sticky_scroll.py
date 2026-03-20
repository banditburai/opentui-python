"""Port of upstream sticky-scroll.test.tsx.

Upstream: packages/solid/tests/sticky-scroll.test.tsx
Tests ported: 4/4 (0 skipped)
"""

from opentui import test_render as _test_render
from opentui.components.box import Box, ScrollBox, ScrollContent
from opentui.components.control_flow import For
from opentui.components.text import Text
from opentui.signals import Signal


async def _strict_render(component_fn, options):
    merged = dict(options)
    return await _test_render(component_fn, merged)


class TestScrollBoxStickyScrollBehavior:
    """Maps to describe("ScrollBox Sticky Scroll Behavior")."""

    async def test_sticky_scroll_bottom_stays_at_bottom_after_scroll_by_scroll_to(self):
        """Maps to it("sticky scroll bottom stays at bottom after scrollBy/scrollTo is called (setter-based)")."""

        items = Signal(["Line 0"], name="items")

        def build():
            return ScrollBox(
                content=ScrollContent(
                    For(
                        each=items,
                        render=lambda item: Box(Text(item), key=f"line-{item}"),
                        key_fn=lambda item: f"line-{item}",
                        key="items",
                    )
                ),
                width=40,
                height=10,
                sticky_scroll=True,
                sticky_start="bottom",
            )

        setup = await _strict_render(build, {"width": 80, "height": 24})
        setup.render_frame()

        # Get the ScrollBox renderable
        scroll_ref = setup.renderer.root.get_children()[0]

        # Call scrollBy and scrollTo - this mimics what happens when content
        # is dynamically added
        scroll_ref.scroll_by(delta_y=100000)
        setup.render_frame()

        scroll_ref.scroll_to(y=scroll_ref.scroll_height)
        setup.render_frame()

        # Now gradually add content
        for i in range(1, 30):
            items.set(items() + [f"Line {i}"])
            setup.render_frame()

            scroll_ref = setup.renderer.root.get_children()[0]
            max_scroll = max(0, scroll_ref.scroll_height - scroll_ref.viewport_height)

            # Check at line 16 (when content definitely overflows)
            if i == 16:
                assert scroll_ref.scroll_offset_y == max_scroll

        # Final check - should still be at bottom
        final_max_scroll = max(0, scroll_ref.scroll_height - scroll_ref.viewport_height)
        assert scroll_ref.scroll_offset_y == final_max_scroll

        setup.destroy()

    async def test_sticky_scroll_can_still_scroll_up_and_down_after_scroll_by_scroll_to(self):
        """Maps to it("sticky scroll can still scroll up and down after scrollBy/scrollTo (setter-based)")."""

        items = Signal([], name="items")

        def build():
            return ScrollBox(
                content=ScrollContent(
                    For(
                        each=items,
                        render=lambda item: Box(Text(item), key=f"line-{item}"),
                        key_fn=lambda item: f"line-{item}",
                        key="items",
                    )
                ),
                width=40,
                height=10,
                sticky_scroll=True,
                sticky_start="bottom",
            )

        setup = await _strict_render(build, {"width": 80, "height": 24})
        setup.render_frame()

        # Add enough content to overflow
        new_items = [f"Line {i}" for i in range(50)]
        items.set(new_items)
        setup.render_frame()

        scroll_ref = setup.renderer.root.get_children()[0]

        # Try to scroll to top
        scroll_ref.scroll_to(y=0)
        setup.render_frame()
        assert scroll_ref.scroll_offset_y == 0

        # Try to scroll down a bit
        scroll_ref.scroll_by(delta_y=5)
        setup.render_frame()
        assert scroll_ref.scroll_offset_y == 5

        # Try to scroll down more
        scroll_ref.scroll_by(delta_y=5)
        setup.render_frame()
        assert scroll_ref.scroll_offset_y == 10

        # Scroll back to bottom
        max_scroll = max(0, scroll_ref.scroll_height - scroll_ref.viewport_height)
        scroll_ref.scroll_to(y=max_scroll)
        setup.render_frame()
        assert scroll_ref.scroll_offset_y == max_scroll

        setup.destroy()

    async def test_accidental_scroll_when_no_scrollable_content_does_not_disable_sticky(self):
        """Maps to it("accidental scroll when no scrollable content does not disable sticky")."""

        items = Signal([], name="items")

        def build():
            return ScrollBox(
                content=ScrollContent(
                    For(
                        each=items,
                        render=lambda item: Box(Text(item), key=f"line-{item}"),
                        key_fn=lambda item: f"line-{item}",
                        key="items",
                    )
                ),
                width=40,
                height=10,
                sticky_scroll=True,
                sticky_start="bottom",
            )

        setup = await _strict_render(build, {"width": 80, "height": 24})
        setup.render_frame()

        scroll_ref = setup.renderer.root.get_children()[0]

        # Simulate accidental scroll attempts when there's no meaningful
        # scrollable content
        scroll_ref.scroll_by(delta_y=100)
        setup.render_frame()
        scroll_ref.scroll_to(y=50)
        setup.render_frame()
        # Mirrors upstream: scroll_ref.scroll_top = 10
        # Using scroll_to goes through the same path as the upstream setter
        scroll_ref.scroll_to(y=10)
        setup.render_frame()

        # _has_manual_scroll should still be false because there was no
        # meaningful scrollable content
        scroll_ref = setup.renderer.root.get_children()[0]
        assert scroll_ref._has_manual_scroll is False

        # Now add content to make it scrollable
        for i in range(30):
            items.set(items() + [f"Line {i}"])
            setup.render_frame()

            scroll_ref = setup.renderer.root.get_children()[0]
            max_scroll = max(0, scroll_ref.scroll_height - scroll_ref.viewport_height)

            # Should still be at bottom due to sticky scroll
            if i == 16:
                assert scroll_ref.scroll_offset_y == max_scroll
                assert scroll_ref._has_manual_scroll is False

        # Final check - should still be at bottom
        final_max_scroll = max(0, scroll_ref.scroll_height - scroll_ref.viewport_height)
        assert scroll_ref.scroll_offset_y == final_max_scroll

        setup.destroy()

    async def test_sticky_scroll_with_sticky_start_set_via_setter(self):
        """Maps to it("sticky scroll with stickyStart set via setter (not constructor)")."""

        items = Signal(["Line 0"], name="items")

        def build():
            sb = ScrollBox(
                content=ScrollContent(
                    For(
                        each=items,
                        render=lambda item: Box(Text(item), key=f"line-{item}"),
                        key_fn=lambda item: f"line-{item}",
                        key="items",
                    ),
                ),
                width=40,
                height=10,
            )
            # Set sticky properties via setters (like SolidJS does),
            # not through the constructor
            sb._sticky_scroll = True
            sb._sticky_start = "bottom"
            return sb

        setup = await _strict_render(build, {"width": 80, "height": 24})
        setup.render_frame()

        scroll_ref = setup.renderer.root.get_children()[0]
        scroll_ref.scroll_by(delta_y=100000)
        setup.render_frame()

        # Add content
        for i in range(1, 30):
            items.set(items() + [f"Line {i}"])
            setup.render_frame()

            scroll_ref = setup.renderer.root.get_children()[0]
            max_scroll = max(0, scroll_ref.scroll_height - scroll_ref.viewport_height)

            if i == 16:
                assert scroll_ref.scroll_offset_y == max_scroll

        setup.destroy()
