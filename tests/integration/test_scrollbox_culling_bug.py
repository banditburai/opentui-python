"""Port of upstream scrollbox-culling-bug.test.ts.

Upstream: packages/core/src/tests/scrollbox-culling-bug.test.ts
Tests ported: 1/1
"""

import re


class TestScrollboxCullingBug:
    """Maps to module-level test (no describe block)."""

    async def test_scrollbox_culling_last_item_not_visible_after_content_grows_with_sticky_scroll(
        self,
    ):
        """Maps to test("scrollbox culling issue: last item not visible...")."""
        from opentui import Box, ScrollBox, create_test_renderer
        from opentui.components.text_renderable import TextRenderable
        from opentui.testing import TestRecorder

        setup = await create_test_renderer(width=50, height=12)

        # Container box with border to see constraints clearly
        container = Box(
            width=48,
            height=10,
            border=True,
        )
        setup.renderer.root.add(container)

        scroll_box = ScrollBox(
            width="100%",
            height="100%",
            sticky_scroll=True,
            sticky_start="bottom",
        )
        container.add(scroll_box)

        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        for i in range(50):
            item = Box(
                id=f"item-{i}",
                height=3,
                border=True,
            )

            text = TextRenderable(content=f"Item {i}")
            item.add(text)

            scroll_box.add(item)
            setup.render_frame()

        # Final render (equivalent of await testRenderer.idle())
        setup.render_frame()

        recorder.stop()

        frames = recorder.recorded_frames

        # With stickyScroll to bottom, there should NEVER be empty space at the bottom
        # when there are items available to render
        for frame_idx in range(len(frames)):
            frame = frames[frame_idx].frame
            lines = frame.split("\n")

            # Find the container's top border line
            container_start = -1
            for line_idx, line in enumerate(lines):
                if line.startswith("\u250c"):  # "┌"
                    container_start = line_idx
                    break

            container_end = container_start + 10 - 1

            if (
                container_start >= 0
                and container_end > container_start
                and container_end < len(lines)
            ):
                content_lines = lines[container_start + 1 : container_end]

                empty_lines_at_bottom = 0

                for k in range(len(content_lines) - 1, -1, -1):
                    line = content_lines[k]
                    # Strip border characters, scrollbar chars, and whitespace
                    content = re.sub(r"^[\u2502\s]*", "", line)
                    content = re.sub(r"[\u2502\u2588\u2584\s]*$", "", content)

                    if len(content) == 0:
                        empty_lines_at_bottom += 1
                    else:
                        break

                expected_items = frame_idx + 1

                # With stickyScroll to bottom, once we have enough items to fill the viewport,
                # there should be NO empty space at the bottom
                # Viewport is 8 lines (10 - 2 for borders), items are 3 lines each
                # So with 3+ items (9 lines of content), we should always fill the viewport
                if expected_items >= 3:
                    assert empty_lines_at_bottom == 0, (
                        f"Frame {frame_idx}: found {empty_lines_at_bottom} empty lines at bottom "
                        f"with {expected_items} items"
                    )

        # With stickyScroll to bottom, the last item should be visible after all items are added
        final_frame = frames[-1].frame
        assert "Item 49" in final_frame, (
            f"Final frame should contain 'Item 49' but it was not found.\n"
            f"Final frame:\n{final_frame}"
        )

        setup.destroy()
