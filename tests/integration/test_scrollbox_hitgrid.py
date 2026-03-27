"""Port of upstream scrollbox-hitgrid.test.ts.

Upstream: packages/core/src/tests/scrollbox-hitgrid.test.ts
Tests: 17
"""

import pytest

from opentui import Box, ScrollBox, create_test_renderer
from opentui.components.base import BaseRenderable


class TestScrollboxHitgrid:
    """ScrollBox Hit Grid Tests"""

    async def test_hit_grid_updates_after_render_when_scrollbox_scrolls(self):
        """Maps to test('hit grid updates after render when scrollbox scrolls')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=40,
                height=20,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            items: list[Box] = []
            for i in range(30):
                item = Box(
                    id=f"item-{i}",
                    height=2,
                    background_color="red" if i % 2 == 0 else "blue",
                )
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            item0 = items[0]
            item4 = items[4]

            assert item0.y == 0
            assert item4.y == 8

            def check_hit_at(x: int, y: int):
                rid = setup.renderer.hit_test(x, y)
                return BaseRenderable.renderables_by_number.get(rid)

            hit_at_item0 = check_hit_at(5, item0.y)
            assert hit_at_item0 is not None
            assert hit_at_item0.id == "item-0"

            hit_at_item4 = check_hit_at(5, item4.y)
            assert hit_at_item4 is not None
            assert hit_at_item4.id == "item-4"

            scroll_box.scroll_top = 10
            setup.render_frame()

            item5 = items[5]
            item9 = items[9]

            # After scroll, items 5 and 9 should be visible at the top
            hit_at_item5 = check_hit_at(5, item5.y - scroll_box.scroll_offset_y)
            assert hit_at_item5 is not None
            assert hit_at_item5.id == "item-5"

            hit_at_item9 = check_hit_at(5, item9.y - scroll_box.scroll_offset_y)
            assert hit_at_item9 is not None
            assert hit_at_item9.id == "item-9"
        finally:
            setup.destroy()

    async def test_hover_updates_after_scroll_when_pointer_moves(self):
        """Maps to test('hover updates after scroll when pointer moves')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=20,
                height=6,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            hover_events: list[str] = []
            hovered_id: str | None = None

            items: list[Box] = []
            for i in range(5):
                item_id = f"item-{i}"
                item = Box(
                    id=item_id,
                    width=20,
                    height=2,
                )

                def make_over(iid):
                    def on_over(event):
                        nonlocal hovered_id
                        hovered_id = iid
                        hover_events.append(f"over:{iid}")

                    return on_over

                def make_out(iid):
                    def on_out(event):
                        nonlocal hovered_id
                        if hovered_id == iid:
                            hovered_id = None
                        hover_events.append(f"out:{iid}")

                    return on_out

                item._on_mouse_over = make_over(item_id)
                item._on_mouse_out = make_out(item_id)
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            pointer_x = items[0].x + 1
            pointer_y = items[0].y + 1

            setup.mock_mouse.move_to(pointer_x, pointer_y)
            assert hovered_id == "item-0"
            assert hover_events == ["over:item-0"]

            scroll_box.scroll_top = 2
            setup.render_frame()

            # Hover updates when pointer moves after scroll and render
            setup.mock_mouse.move_to(pointer_x, pointer_y)
            assert hovered_id == "item-1"
            assert hover_events == ["over:item-0", "out:item-0", "over:item-1"]
        finally:
            setup.destroy()

    async def test_hover_updates_after_scroll_without_pointer_movement(self):
        """Maps to test('hover updates after scroll without pointer movement')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=20,
                height=6,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            hover_events: list[str] = []
            hovered_id: str | None = None

            items: list[Box] = []
            for i in range(5):
                item_id = f"item-{i}"
                item = Box(
                    id=item_id,
                    width=20,
                    height=2,
                )

                def make_over(iid):
                    def on_over(event):
                        nonlocal hovered_id
                        hovered_id = iid
                        hover_events.append(f"over:{iid}")

                    return on_over

                def make_out(iid):
                    def on_out(event):
                        nonlocal hovered_id
                        if hovered_id == iid:
                            hovered_id = None
                        hover_events.append(f"out:{iid}")

                    return on_out

                item._on_mouse_over = make_over(item_id)
                item._on_mouse_out = make_out(item_id)
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            pointer_x = items[0].x + 1
            pointer_y = items[0].y + 1

            setup.mock_mouse.move_to(pointer_x, pointer_y)
            assert hovered_id == "item-0"
            assert hover_events == ["over:item-0"]

            scroll_box.scroll_top = 2
            setup.render_frame()

            # Hover updates immediately after render without pointer movement
            assert hovered_id == "item-1"
            assert hover_events == ["over:item-0", "out:item-0", "over:item-1"]
        finally:
            setup.destroy()

    async def test_hover_recheck_uses_neutral_button_and_modifiers(self):
        """Maps to test('hover recheck uses neutral button and modifiers')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=20,
                height=6,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            hover_events: list[dict] = []
            hovered_id: str | None = None

            items: list[Box] = []
            for i in range(5):
                item_id = f"item-{i}"
                item = Box(
                    id=item_id,
                    width=20,
                    height=2,
                )

                def make_over(iid):
                    def on_over(event):
                        nonlocal hovered_id
                        hovered_id = iid
                        hover_events.append(
                            {
                                "type": "over",
                                "button": event.button,
                                "modifiers": {
                                    "shift": event.shift,
                                    "alt": event.alt,
                                    "ctrl": event.ctrl,
                                },
                            }
                        )

                    return on_over

                def make_out(iid):
                    def on_out(event):
                        nonlocal hovered_id
                        if hovered_id == iid:
                            hovered_id = None
                        hover_events.append(
                            {
                                "type": "out",
                                "button": event.button,
                                "modifiers": {
                                    "shift": event.shift,
                                    "alt": event.alt,
                                    "ctrl": event.ctrl,
                                },
                            }
                        )

                    return on_out

                item._on_mouse_over = make_over(item_id)
                item._on_mouse_out = make_out(item_id)
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            pointer_x = items[0].x + 1
            pointer_y = items[0].y + 1

            # Move with shift modifier
            from opentui.events import MouseEvent

            move_ev = MouseEvent(type="move", x=pointer_x, y=pointer_y, shift=True)
            setup.renderer._dispatch_mouse_event(move_ev)
            assert hovered_id == "item-0"

            # Press down with right button and shift
            down_ev = MouseEvent(type="down", x=pointer_x, y=pointer_y, button=2, shift=True)
            setup.renderer._dispatch_mouse_event(down_ev)

            scroll_box.scroll_top = 2
            setup.render_frame()

            assert hovered_id == "item-1"
            assert len(hover_events) == 3
            out_event = hover_events[1]
            over_event = hover_events[2]
            # Synthetic hover recheck uses neutral button (0)
            assert out_event["button"] == 0
            assert out_event["modifiers"] == {"shift": True, "alt": False, "ctrl": False}
            assert over_event["button"] == 0
            assert over_event["modifiers"] == {"shift": True, "alt": False, "ctrl": False}
        finally:
            setup.destroy()

    async def test_hover_recheck_over_event_has_no_source_when_not_dragging(self):
        """Maps to test('hover recheck over event has no source when not dragging')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=20,
                height=6,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            hover_events: list[dict] = []

            items: list[Box] = []
            for i in range(5):
                item_id = f"item-{i}"
                item = Box(
                    id=item_id,
                    width=20,
                    height=2,
                )

                def make_over(iid):
                    def on_over(event):
                        hover_events.append(
                            {
                                "type": "over",
                                "source": event.source,
                            }
                        )

                    return on_over

                def make_out(iid):
                    def on_out(event):
                        hover_events.append(
                            {
                                "type": "out",
                                "source": event.source,
                            }
                        )

                    return on_out

                item._on_mouse_over = make_over(item_id)
                item._on_mouse_out = make_out(item_id)
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            pointer_x = items[0].x + 1
            pointer_y = items[0].y + 1

            # Move to item-0 (not dragging)
            setup.mock_mouse.move_to(pointer_x, pointer_y)
            assert len(hover_events) == 1
            assert hover_events[0]["type"] == "over"
            assert hover_events[0]["source"] is None

            # Scroll to trigger hover recheck
            scroll_box.scroll_top = 2
            setup.render_frame()

            assert len(hover_events) == 3
            # out event from item-0
            assert hover_events[1]["type"] == "out"
            assert hover_events[1]["source"] is None
            # over event to item-1 - source should be None (not dragging)
            assert hover_events[2]["type"] == "over"
            assert hover_events[2]["source"] is None
        finally:
            setup.destroy()

    async def test_hover_updates_on_multiple_scroll_changes(self):
        """Maps to test('hover updates on multiple scroll changes')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=20,
                height=6,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            hover_events: list[str] = []
            hovered_id: str | None = None

            items: list[Box] = []
            for i in range(5):
                item_id = f"item-{i}"
                item = Box(
                    id=item_id,
                    width=20,
                    height=2,
                )

                def make_over(iid):
                    def on_over(event):
                        nonlocal hovered_id
                        hovered_id = iid
                        hover_events.append(f"over:{iid}")

                    return on_over

                def make_out(iid):
                    def on_out(event):
                        nonlocal hovered_id
                        if hovered_id == iid:
                            hovered_id = None
                        hover_events.append(f"out:{iid}")

                    return on_out

                item._on_mouse_over = make_over(item_id)
                item._on_mouse_out = make_out(item_id)
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            pointer_x = items[0].x + 1
            pointer_y = items[0].y + 1

            setup.mock_mouse.move_to(pointer_x, pointer_y)
            assert hovered_id == "item-0"
            assert hover_events == ["over:item-0"]

            # First scroll
            scroll_box.scroll_top = 2
            setup.render_frame()
            assert hovered_id == "item-1"

            # Second scroll
            scroll_box.scroll_top = 4
            setup.render_frame()

            assert hovered_id == "item-2"
            assert hover_events == [
                "over:item-0",
                "out:item-0",
                "over:item-1",
                "out:item-1",
                "over:item-2",
            ]
        finally:
            setup.destroy()

    async def test_mouse_move_during_scroll_triggers_normal_hover(self):
        """Maps to test('mouse move during scroll triggers normal hover')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=20,
                height=6,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            hover_events: list[str] = []
            hovered_id: str | None = None

            items: list[Box] = []
            for i in range(5):
                item_id = f"item-{i}"
                item = Box(
                    id=item_id,
                    width=20,
                    height=2,
                )

                def make_over(iid):
                    def on_over(event):
                        nonlocal hovered_id
                        hovered_id = iid
                        hover_events.append(f"over:{iid}")

                    return on_over

                def make_out(iid):
                    def on_out(event):
                        nonlocal hovered_id
                        if hovered_id == iid:
                            hovered_id = None
                        hover_events.append(f"out:{iid}")

                    return on_out

                item._on_mouse_over = make_over(item_id)
                item._on_mouse_out = make_out(item_id)
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            pointer_x = items[0].x + 1
            pointer_y = items[0].y + 1

            setup.mock_mouse.move_to(pointer_x, pointer_y)
            assert hovered_id == "item-0"
            assert hover_events == ["over:item-0"]

            # Scroll triggers render which triggers immediate hover recheck
            scroll_box.scroll_top = 2
            setup.render_frame()
            assert hovered_id == "item-1"
            assert hover_events == ["over:item-0", "out:item-0", "over:item-1"]

            # Mouse move doesn't duplicate events since we're already on item-1
            setup.mock_mouse.move_to(pointer_x, pointer_y)
            assert hovered_id == "item-1"
            assert hover_events == ["over:item-0", "out:item-0", "over:item-1"]
        finally:
            setup.destroy()

    async def test_hover_updates_immediately_after_render(self):
        """Maps to test('hover updates immediately after render')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=20,
                height=6,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            hovered_id: str | None = None

            items: list[Box] = []
            for i in range(5):
                item_id = f"item-{i}"
                item = Box(
                    id=item_id,
                    width=20,
                    height=2,
                )

                def make_over(iid):
                    def on_over(event):
                        nonlocal hovered_id
                        hovered_id = iid

                    return on_over

                def make_out(iid):
                    def on_out(event):
                        nonlocal hovered_id
                        if hovered_id == iid:
                            hovered_id = None

                    return on_out

                item._on_mouse_over = make_over(item_id)
                item._on_mouse_out = make_out(item_id)
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            pointer_x = items[0].x + 1
            pointer_y = items[0].y + 1

            setup.mock_mouse.move_to(pointer_x, pointer_y)
            assert hovered_id == "item-0"

            # Hover updates immediately after render - no delay needed
            scroll_box.scroll_top = 2
            setup.render_frame()
            assert hovered_id == "item-1"
        finally:
            setup.destroy()

    async def test_hit_grid_handles_multiple_scroll_operations_correctly(self):
        """Maps to test('hit grid handles multiple scroll operations correctly')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=40,
                height=20,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            items: list[Box] = []
            for i in range(40):
                item = Box(id=f"item-{i}", height=2)
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            def check_hit_at(x: int, y: int):
                rid = setup.renderer.hit_test(x, y)
                return BaseRenderable.renderables_by_number.get(rid)

            scroll_box.scroll_top = 20
            setup.render_frame()
            # item-10 should now be at the top (scroll=20, each item is 2 rows)
            hit = check_hit_at(5, 0)
            assert hit is not None
            assert hit.id == "item-10"

            scroll_box.scroll_top = 40
            setup.render_frame()
            hit = check_hit_at(5, 0)
            assert hit is not None
            assert hit.id == "item-20"

            scroll_box.scroll_top = 0
            setup.render_frame()
            hit = check_hit_at(5, 0)
            assert hit is not None
            assert hit.id == "item-0"
        finally:
            setup.destroy()

    async def test_hit_grid_respects_scrollbox_viewport_clipping_when_offset(self):
        """Maps to test('hit grid respects scrollbox viewport clipping when offset')."""
        setup = await create_test_renderer(50, 30)
        try:
            container = Box(
                flex_direction="column",
                width=50,
                height=30,
            )
            setup.renderer.root.add(container)

            header = Box(id="header", height=5, width=50)
            container.add(header)

            scroll_box = ScrollBox(
                width=40,
                height=10,
                scroll_y=True,
            )
            container.add(scroll_box)

            items: list[Box] = []
            for i in range(10):
                item = Box(id=f"item-{i}", height=2)
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            def check_hit_at(x: int, y: int):
                rid = setup.renderer.hit_test(x, y)
                return BaseRenderable.renderables_by_number.get(rid)

            header_hit = check_hit_at(2, header.y + 1)
            assert header_hit is not None
            assert header_hit.id == "header"

            scroll_box.scroll_top = 4
            setup.render_frame()

            header_hit_after_scroll = check_hit_at(2, header.y + 1)
            assert header_hit_after_scroll is not None
            assert header_hit_after_scroll.id == "header"

            viewport = scroll_box.viewport
            viewport_hit = check_hit_at(2, viewport["y"] + 1)
            assert viewport_hit is not None
            assert viewport_hit.id == "item-2"
        finally:
            setup.destroy()

    async def test_hover_recheck_skips_while_dragging_captured_renderable(self):
        """Maps to test('hover recheck skips while dragging captured renderable')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=20,
                height=6,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            hover_events: list[str] = []

            items: list[Box] = []
            for i in range(5):
                item_id = f"item-{i}"
                item = Box(
                    id=item_id,
                    width=20,
                    height=2,
                )

                def make_over(iid):
                    def on_over(event):
                        hover_events.append(f"over:{iid}")

                    return on_over

                def make_out(iid):
                    def on_out(event):
                        hover_events.append(f"out:{iid}")

                    return on_out

                item._on_mouse_over = make_over(item_id)
                item._on_mouse_out = make_out(item_id)
                # Need a drag handler so the renderable gets captured
                item._on_mouse_drag = lambda event: None
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            pointer_x = items[0].x + 1
            pointer_y = items[0].y + 1

            setup.mock_mouse.move_to(pointer_x, pointer_y)
            setup.mock_mouse.press_down(pointer_x, pointer_y)
            # Drag to capture the renderable
            setup.mock_mouse.move_to(pointer_x, pointer_y)

            scroll_box.scroll_top = 2
            setup.render_frame()

            # Hover recheck is skipped when there's a captured renderable (during drag)
            assert hover_events == ["over:item-0"]
        finally:
            setup.destroy()

    async def test_captured_renderable_is_not_in_hit_grid_during_scroll(self):
        """Maps to test('captured renderable is not in hit grid during scroll')."""
        setup = await create_test_renderer(50, 30)
        try:
            scroll_box = ScrollBox(
                width=40,
                height=10,
                scroll_y=True,
            )
            setup.renderer.root.add(scroll_box)

            items: list[Box] = []
            for i in range(20):
                item = Box(id=f"item-{i}", height=2)
                # Add drag handler so capture works
                item._on_mouse_drag = lambda event: None
                items.append(item)
                scroll_box.add(item)

            setup.render_frame()

            viewport = scroll_box.viewport
            pointer_x = 2
            pointer_y = viewport["y"] + 1

            setup.mock_mouse.press_down(pointer_x, pointer_y)
            setup.mock_mouse.move_to(pointer_x, pointer_y + 1)

            scroll_box.scroll_top = 4
            setup.render_frame()

            rid = setup.renderer.hit_test(pointer_x, pointer_y)
            hit = BaseRenderable.renderables_by_number.get(rid)
            assert hit is not None
            assert hit.id == "item-2"
        finally:
            setup.destroy()

    async def test_hit_grid_stays_clipped_after_render(self):
        """Maps to test('hit grid stays clipped after render')."""
        setup = await create_test_renderer(50, 30)
        try:
            container = Box(
                id="container",
                width=10,
                height=4,
                overflow="hidden",
            )
            setup.renderer.root.add(container)

            child = Box(
                id="child",
                width=20,
                height=4,
            )
            container.add(child)

            setup.render_frame()

            inside_hit_id = setup.renderer.hit_test(container.x + 1, container.y + 1)
            inside_hit = BaseRenderable.renderables_by_number.get(inside_hit_id)
            assert inside_hit is not None
            assert inside_hit.id == "child"

            outside_hit_id = setup.renderer.hit_test(
                container.x + int(container._layout_width) + 1,
                container.y + 1,
            )
            assert outside_hit_id == 0
        finally:
            setup.destroy()

    async def test_buffered_overflow_scissor_uses_screen_coordinates_for_hit_grid(self):
        """Maps to test('buffered overflow scissor uses screen coordinates for hit grid')."""
        setup = await create_test_renderer(50, 30)
        try:
            container = Box(
                id="buffered-container",
                width=10,
                height=4,
                overflow="hidden",
                position="absolute",
                left=10,
                top=5,
            )
            setup.renderer.root.add(container)

            child = Box(
                id="buffered-child",
                width=10,
                height=4,
            )
            container.add(child)

            setup.render_frame()

            hit_id = setup.renderer.hit_test(container.x + 1, container.y + 1)
            hit = BaseRenderable.renderables_by_number.get(hit_id)
            assert hit is not None
            assert hit.id == "buffered-child"
        finally:
            setup.destroy()

    async def test_hover_updates_after_translate_animation(self):
        """Maps to test('hover updates after translate animation').

        Uses translate_y on a Box to simulate the upstream MovingBoxRenderable
        that moves via translateY in onUpdate.
        """
        setup = await create_test_renderer(50, 30)
        try:
            hover_events: list[str] = []
            hovered_id: str | None = None

            under = Box(
                id="under",
                position="absolute",
                left=2,
                top=2,
                width=6,
                height=2,
                z_index=0,
            )

            def under_over(event):
                nonlocal hovered_id
                hovered_id = "under"
                hover_events.append("over:under")

            def under_out(event):
                nonlocal hovered_id
                if hovered_id == "under":
                    hovered_id = None
                hover_events.append("out:under")

            under._on_mouse_over = under_over
            under._on_mouse_out = under_out
            setup.renderer.root.add(under)

            moving = Box(
                id="moving",
                position="absolute",
                left=2,
                top=2,
                width=6,
                height=2,
                z_index=1,
            )

            def moving_over(event):
                nonlocal hovered_id
                hovered_id = "moving"
                hover_events.append("over:moving")

            def moving_out(event):
                nonlocal hovered_id
                if hovered_id == "moving":
                    hovered_id = None
                hover_events.append("out:moving")

            moving._on_mouse_over = moving_over
            moving._on_mouse_out = moving_out
            setup.renderer.root.add(moving)

            setup.render_frame()

            pointer_x = moving.x + 1
            pointer_y = moving.y + 1

            setup.mock_mouse.move_to(pointer_x, pointer_y)
            assert hovered_id == "moving"
            assert hover_events == ["over:moving"]

            # Move the box down by 3 via top offset (simulates translateY animation)
            moving.pos_top = 5  # move from top=2 to top=5
            setup.render_frame()

            assert hovered_id == "under"
            assert hover_events == ["over:moving", "out:moving", "over:under"]
        finally:
            setup.destroy()

    async def test_hover_updates_after_z_index_change(self):
        """Maps to test('hover updates after z-index change')."""
        setup = await create_test_renderer(50, 30)
        try:
            hover_events: list[str] = []
            hovered_id: str | None = None

            back = Box(
                id="back",
                position="absolute",
                left=2,
                top=2,
                width=6,
                height=2,
                z_index=0,
            )

            def back_over(event):
                nonlocal hovered_id
                hovered_id = "back"
                hover_events.append("over:back")

            def back_out(event):
                nonlocal hovered_id
                if hovered_id == "back":
                    hovered_id = None
                hover_events.append("out:back")

            back._on_mouse_over = back_over
            back._on_mouse_out = back_out
            setup.renderer.root.add(back)

            front = Box(
                id="front",
                position="absolute",
                left=2,
                top=2,
                width=6,
                height=2,
                z_index=1,
            )

            def front_over(event):
                nonlocal hovered_id
                hovered_id = "front"
                hover_events.append("over:front")

            def front_out(event):
                nonlocal hovered_id
                if hovered_id == "front":
                    hovered_id = None
                hover_events.append("out:front")

            front._on_mouse_over = front_over
            front._on_mouse_out = front_out
            setup.renderer.root.add(front)

            setup.render_frame()

            pointer_x = front.x + 1
            pointer_y = front.y + 1

            setup.mock_mouse.move_to(pointer_x, pointer_y)
            assert hovered_id == "front"
            assert hover_events == ["over:front"]

            back.z_index = 2
            setup.render_frame()

            assert hovered_id == "back"
            assert hover_events == ["over:front", "out:front", "over:back"]
        finally:
            setup.destroy()

    async def test_mouse_down_dispatch_uses_z_index_order(self):
        """Mouse dispatch should follow the same front-to-back order as hit-testing."""
        setup = await create_test_renderer(50, 30)
        try:
            clicks: list[str] = []

            back = Box(
                id="back",
                position="absolute",
                left=2,
                top=2,
                width=6,
                height=2,
                z_index=0,
            )
            back._on_mouse_down = lambda event: clicks.append("back")
            setup.renderer.root.add(back)

            front = Box(
                id="front",
                position="absolute",
                left=2,
                top=2,
                width=6,
                height=2,
                z_index=1,
            )
            front._on_mouse_down = lambda event: clicks.append("front")
            setup.renderer.root.add(front)

            setup.render_frame()

            setup.mock_mouse.click(front.x + 1, front.y + 1)
            assert clicks == ["front"]

            clicks.clear()
            back.z_index = 2
            setup.render_frame()

            setup.mock_mouse.click(front.x + 1, front.y + 1)
            assert clicks == ["back"]
        finally:
            setup.destroy()

    async def test_scrolling_does_not_steal_clicks_outside_the_list(self):
        """Maps to test('scrolling does not steal clicks outside the list')."""
        setup = await create_test_renderer(50, 30)
        try:
            last_click = "none"

            overlay = Box(
                id="overlay",
                position="absolute",
                left=0,
                top=0,
                width=50,
                height=30,
                z_index=100,
            )

            def overlay_down(event):
                nonlocal last_click
                last_click = "overlay"

            overlay._on_mouse_down = overlay_down
            setup.renderer.root.add(overlay)

            dialog = Box(
                id="dialog",
                position="absolute",
                left=5,
                top=4,
                width=30,
                height=14,
                flex_direction="column",
                padding=1,
                gap=1,
            )

            def dialog_down(event):
                nonlocal last_click
                last_click = "dialog"
                event.stop_propagation()

            dialog._on_mouse_down = dialog_down
            overlay.add(dialog)

            header = Box(
                id="dialog-header",
                width=30,
                height=2,
            )

            def header_down(event):
                nonlocal last_click
                last_click = "header"
                event.stop_propagation()

            header._on_mouse_down = header_down
            dialog.add(header)

            scroll_box = ScrollBox(
                id="dialog-scrollbox",
                width=30,
                height=7,
                scroll_y=True,
            )

            def scrollbox_down(event):
                nonlocal last_click
                last_click = "scrollbox"
                event.stop_propagation()

            scroll_box._on_mouse_down = scrollbox_down
            dialog.add(scroll_box)

            for i in range(20):
                item = Box(id=f"line-{i}", width=30, height=1)
                scroll_box.add(item)

            setup.render_frame()

            viewport = scroll_box.viewport
            setup.mock_mouse.click(viewport["x"] + 1, viewport["y"] + 1)
            assert last_click == "scrollbox"

            header_click_y = header.y + 1
            target_scroll_top = max(1, viewport["y"] - header_click_y)
            scroll_box.scroll_top = target_scroll_top

            setup.mock_mouse.click(header.x + 1, header_click_y)
            assert last_click == "header"

            setup.mock_mouse.click(dialog.x + 1, dialog.y - 1)
            assert last_click == "overlay"

            setup.render_frame()
        finally:
            setup.destroy()
